import archinstall
import pathlib
import os
from pprint import pprint
# from pudb import set_trace
import logging
from copy import deepcopy, copy
import re

from typing import Any, TYPE_CHECKING, Dict, Optional, List

if TYPE_CHECKING:
	_: Any

from archinstall.lib.user_interaction.disk_conf import get_default_partition_layout
from archinstall.lib.user_interaction.subvolume_config import SubvolumeList

GLOBAL_BLOCK_MAP = {}
"""
Auxiliary functions
"""
def list_free_space(device :archinstall.BlockDevice, unit :str = 'compact'):
	free_array = []
	if unit and unit.lower() in ('s','b','kib','mib','gib','tib','kb','mb','gb','tb','%','compact'):
		unit_string = f"unit {unit}"
	else:
		archinstall.log(f"Unit specified {unit} is not supported by Parted, switching to 'compact'", level=logging.DEBUG)
		unit_string = 'compact'
	try:
		for line in archinstall.SysCommand(f"parted -s --machine {device.path} {unit_string} print free"):
			line_split = line.decode('UTF-8').strip('\r\n;').split(':')
			if line_split[0] == device.path:
				full_size = line_split[1]
				sector_size = line_split[3]
			elif len(line_split) >= 4 and (line_split[4] == '' or 'free' in line_split[4]):
				if unit == 'compact':
					free_array.append((line_split[1],line_split[2],line_split[3]))
				else:
					free_array.append(list(map(lambda x,u=unit:int(convert_units(x,u)), [line_split[1],line_split[2],line_split[3]])))
				# (start, end, size))
	except archinstall.SysCallError as error:
		archinstall.log(f"Could not get free space on {device.path}: {error}", level=logging.DEBUG)
	return full_size,sector_size,free_array

def unit_best_fit(raw_value,default_unit='s'):
	base_value = convert_units(raw_value,'s',default_unit)
	conversion_rates = {
		'KiB' : 2,
		'MiB' : 2**11,
		'GiB' : 2**21,
		'TiB' : 2**31,
	}
	for unit in ('TiB','GiB','MiB','KiB'):
		if base_value > conversion_rates[unit]:
			return f"{convert_units(base_value,unit,'s',precision=1)} {unit}"
	return f"{base_value} s"


def convert_units(value,to_unit='b',d_from_unit='b',sector_size=512,precision=3):
	conversion_rates = {
		'kb' : 10**3,
		'mb' : 10**6,
		'gb' : 10**9,
		'tb' : 10**12,
		'kib' : 2**10,
		'mib' : 2**20,
		'gib' : 2**30,
		'tib' : 2**40,
		's' : sector_size
	}

	def to_bytes(number,unit):
		if unit == 'b':
			return number
		else:
			return number * conversion_rates[unit]

	def from_bytes(number,unit,precision=precision):
		if unit == 'b':
			return number
		if unit == 's':
			precision = 0
		return round(number / conversion_rates[unit],precision)

	if isinstance(value,(int,float)):
		target_value = value
		from_unit = d_from_unit.lower().strip() # if d_from_unit else 'b'
	else:
		result = re.split(r'(\d+\.\d+|\d+)',value.replace(',','').strip())
		from_unit = result[2].lower().strip() if result[2].strip() else d_from_unit
		target_value = float(result[1])

	to_unit = to_unit.lower().strip()

	if (from_unit == '%') or (to_unit == '%'):
		archinstall.log(f"convert units does not support % notation")
		return value

	if from_unit in ('s','b','kib','mib','gib','tib','kb','mb','gb','tb'):
		pass
	else:
		raise archinstall.UserError(f"Invalid use of {from_unit} as from unit in convert_units")
	if to_unit in ('s','b','kib','mib','gib','tib','kb','mb','gb','tb'):
		pass
	else:
		raise archinstall.UserError(f"Invalid use of {to_unit} as to unit in convert_units")

	if to_unit == from_unit:
		return target_value
	if to_unit in ('s','b'):
		return int(round(from_bytes(to_bytes(target_value,from_unit),to_unit.strip().lower(),precision),0))
	else:
		return from_bytes(to_bytes(target_value,from_unit),to_unit.strip().lower(),precision)

def get_device_info(device):
	try:
		information = archinstall.blkid(f'blkid -p -o export {device}')
	# TODO: No idea why F841 is raised here:
	except archinstall.SysCallError as error: # noqa: F841
		if error.exit_code in (512, 2):
			# Assume that it's a loop device, and try to get info on it
			try:
				information = archinstall.get_loop_info(device)
				if not information:
					raise archinstall.SysCallError("Could not get loop information", exit_code=1)

			except archinstall.SysCallError:
				information = archinstall.get_blockdevice_uevent(pathlib.Path(device).name)
		else:
			raise error

	information = archinstall.enrich_blockdevice_information(information)
	return information

# perform_gap_assignement
def create_gaps(structure,disk,disk_size):
	struct_full = []
	presumed_start = 34  # TODO this is for GPT formatted disks. Need to establish a standard behavior
	for part in structure:
		if int(part['start']) > presumed_start:
			gap = {
				"id": f"{disk} {presumed_start:>15}",
				"class" : 'gap',
				"type" : None,
				"start" : presumed_start,
				"size" : int(part['start']) - presumed_start ,
				# "sizeG": round(int(device_info['PART_ENTRY_SIZE']) * 512 / archinstall.GIGA,1),
				"boot" : False,
				"encrypted" : False,
				"wipe" : False,
				"actual_mountpoint" : None,
				"mountpoint" : None,
				"filesystem" : {},
				"uuid": None,
				# "partnr": device_info['PART_ENTRY_NUMBER'],
				"path": None,
				"subvolumes":{}
			}
			struct_full.append(gap)
		elif int(part['start']) < presumed_start:
			print(f"Might have off by one error ,{part['start']},{presumed_start}")
		struct_full.append(part)
		# TODO percentajes if it is not at the end. Might be off by one. I believe it never reaches here
		if isinstance(part['size'],str) and part['size'].endswith('%'): # if it is at the end. Might be off by one
			size = ((disk_size - 34) - int(part['start'])) * int(part['size'][:-1]) * 0.01
			presumed_start = int(part['start']) + int(size)
		else:
			presumed_start = int(part['start']) + int(part['size'])

	# don't ask me why the 34 sector difference. Probably a copy of a master record or such
	if presumed_start < (disk_size - 34) :
		gap = {
			"id": f"{disk} {presumed_start:>15}",
			"class" : 'gap',
			"type" : None,
			"start" : presumed_start,
			"size" : disk_size - 34 - presumed_start,
			# "sizeG": round(int(device_info['PART_ENTRY_SIZE']) * 512 / archinstall.GIGA,1),
			"boot" : False,
			"encrypted" : False,
			"wipe" : False,
			"actual_mountpoint" : None,
			"mountpoint" : None,
			"filesystem" : {},
			"uuid": None,
			# "partnr": device_info['PART_ENTRY_NUMBER'],
			"path": None,
			"subvolumes":{}
		}
		struct_full.append(gap)
	return struct_full

def create_global_block_map(disks=None):
	def list_subvols(object):
		subvol_info = [archinstall.Subvolume(subvol.name,str(subvol.full_path)) for subvol in object.subvolumes]
		return subvol_info

	archinstall.log(_("Waiting for the system to get actual block device info"),fg="yellow")
	result = archinstall.all_blockdevices(partitions=True)
	hard_drives = []
	disk_layout = {}
	encrypted_partitions = set()
	my_disks = {item.path for item in disks} if disks else {}

	for res in sorted(result):
		device_info = {}
		for entry in get_device_info(res):
			device_info = device_info | get_device_info(res)[entry]
		if isinstance(result[res],archinstall.BlockDevice): # disk
			if my_disks and res not in my_disks:
				continue
			hard_drives.append(result[res])
			if result[res].size == 0:
				continue
			try:
				disk_layout[res] = {'partitions':[],
									'structure':[], # physical structure
							'wipe':False,
							'pttype':result[res].info.get('PTTYPE',None),
							'ptuuid':result[res].info.get('PTUUID',None),
							'sizeG':result[res].size,
							'size':device_size_sectors(res),
							'sector_size':device_sector_size(res)}

			except KeyError as e:
				print(f"Horror at {res} Terror at {e}")
				pprint(device_info)
				exit(1)

		if isinstance(result[res],archinstall.Partition):
			if my_disks and result[res].parent not in my_disks:
				continue
			try:
				if device_info['TYPE'] == 'crypto_LUKS':
					encrypted = True
					encrypted_partitions.add(res)
				else:
					encrypted = False
				# TODO make the subvolumes work
				if result[res].filesystem == 'btrfs':
					subvol_info = list_subvols(result[res])
				else:
					subvol_info = {}
				partition = {
					"id": f"{result[res].parent} {device_info['PART_ENTRY_OFFSET']:>15}",
					"type" : device_info.get('PART_ENTRY_NAME',device_info.get('PART_ENTRY_TYPE','')),
					"start" : device_info['PART_ENTRY_OFFSET'],
					"size" : device_info['PART_ENTRY_SIZE'],
					# "sizeG": round(int(device_info['PART_ENTRY_SIZE']) * 512 / archinstall.GIGA,1),
					"boot" : result[res].boot,
					"encrypted" : encrypted,
					"wipe" : False,
					"actual_mountpoint" : result[res].mountpoint,  # <-- this is false
					"mountpoint" : None,
					"filesystem" : {
						"format" : result[res].filesystem
					},
					"uuid": result[res].uuid,
					"partnr": device_info['PART_ENTRY_NUMBER'],
					"path": device_info['PATH'],
					"actual_subvolumes": subvol_info,
					"subvolumes":[]
				}
				disk_layout[result[res].parent]['structure'].append(partition)
			except KeyError as e:
				print(f"Horror at {res} Terror at {e}")
				pprint(device_info)
				exit()
			# TODO encrypted volumes
			# TODO btrfs subvolumes
			# TODO aditional fields
			# TODO swap volumes
			# gaps
		if isinstance(result[res],archinstall.DMCryptDev):
			# TODO we need to ensure the device is opened and later closed to get the info
			# Problems with integration. Returned prior to normal partitions
			print('==>')
			print(res)
			print(result[res])
			print('\t',result[res].name)
			print('\t',result[res].path)
			print('\t',result[res].MapperDev)
			print('\t\t',result[res].MapperDev.name)
			print('\t\t',result[res].MapperDev.partition)
			print('\t\t',result[res].MapperDev.partition.path)  # <-- linkage
			print('\t\t',result[res].MapperDev.path)
			print('\t\t',result[res].MapperDev.filesystem) # <--
			print('\t\t',list_subvols(result[res].MapperDev)) # <-- is empty if not mounted/
			print('\t\t',result[res].MapperDev.mount_information) # <-- error if not mounted
			print('\t\t',result[res].MapperDev.mountpoint) # <-- error if not mounted
			print('\t',result[res].mountpoint)
			print('\t',result[res].filesystem)
			pprint(device_info)
			print()
			# TODO move relevant information to the corresponding partition
			input('yep')
	GLOBAL_BLOCK_MAP.update(disk_layout)

def normalize_from_layout(partition_list,disk):
	last_sector = GLOBAL_BLOCK_MAP[disk]['size'] - 1

	def subvol_normalize(part):
		subvol_info = part.get('btrfs',{}).get('subvolumes',{})
		norm_subvol = []
		if subvol_info and isinstance(subvol_info,dict): # old syntax
			for subvol in subvol_info:
				if subvol_info[subvol] is None:
					norm_subvol.append(archinstall.Subvolume(subvol))
				elif isinstance(subvol_info[subvol],str):
					norm_subvol.append(archinstall.Subvolume(subvol,subvol_info[subvol]))
				else:
					# TODO compress and nodatacow in this case
					mi_compress = True if 'compress' in subvol_info.get('options',[]) else False
					mi_nodatacow = True if 'nodatacow' in subvol_info.get('options',[]) else False
					norm_subvol.append(archinstall.Subvolue(subvol,subvol_info[subvol].get('mountpoint'),mi_compress,mi_nodatacow))
		elif subvol_info:
			for subvol in subvol_info:
				if isinstance(subvol,archinstall.Subvolume):
					norm_subvol.append(subvol)
				else:
					norm_subvol.append(archinstall.Subvolume(subvol.get('name'),subvol.get('mountpoint'),subvol.get('compress',False),subvol.get('nodatacow',False)))
		return norm_subvol

	def size_normalize(part,disk):
		start = convert_units(part['start'],'s','s')
		if isinstance(part['size'],str) and part['size'].endswith('%'):
			size = round((last_sector - start + 1) * float(part['size'][:-1]) * 0.01,0)
			sizeG = part['size']
		else:
			size = convert_units(part['size'],'s','s')
			sizeG = part['size'] if part['size'].lower().endswith('b') else None
		return start, size, sizeG
	result = []
	for part in partition_list:
		start,size,sizeG = size_normalize(part,disk)
		result.append({
			"id": f"{disk} {start:>15}",
			"class": "partition",
			"type" : part.get('type','primary'),
			"start" : start,
			"size" : size,
			"sizeG": sizeG,
			"boot" : part.get('boot',False),
			"encrypted" : part.get('encrypted',False),
			"wipe" : part.get('wipe',False),
			"actual_mountpoint" : None,
			"mountpoint" : part.get('mountpoint'),
			"filesystem" : {
				"format" : part.get('filesystem',{}).get('format'),
				"format_options":part.get('filesystem',{}).get('format_options',[]),
				"mount_options":part.get('filesystem',{}).get('mount_options',[]),
			},
			"uuid": None,
			# "partnr": device_info['PART_ENTRY_NUMBER'],
			"path": None,
			"subvolumes":subvol_normalize(part)
		})
	return result

def integrate_layout_in_global_map(harddrives,layout):
	result_dict = {}
	# disk in harddrives must exist in the machine
	# TODO ENHACEMENT offer alternative
	hard_list = [drive.path for drive in harddrives]
	if hard_list:

		for disk in hard_list:
			# harddrives brings BlockDevice
			if disk not in GLOBAL_BLOCK_MAP:
				archinstall.log(f"harddrives: Block Device {disk} can not be accessed in this machine",fg='red',level=logging.ERROR)
				exit(1)
	if layout:
		for disk in layout:
			if disk not in GLOBAL_BLOCK_MAP:
				archinstall.log(f"layout: Block Device {disk} can not be accessed in this machine",fg='red',level=logging.ERROR)
				exit(1)

	for disk in GLOBAL_BLOCK_MAP:
		if not hard_list or disk in hard_list:
			result_dict[disk] = {}
			for key in GLOBAL_BLOCK_MAP[disk]:
				if key == 'structure':
					result_dict[disk]['partitions'] = copy(GLOBAL_BLOCK_MAP[disk]['structure'])
				else:
					result_dict[disk][key] = GLOBAL_BLOCK_MAP[disk][key]
			if layout and disk in layout:
				# TODO normalize contents of layout
				normalized_partitions = normalize_from_layout(layout[disk].get('partitions',[]),disk)
				if layout[disk].get('wipe',False):
					result_dict[disk]['wipe'] = True
					result_dict[disk]['partitions'] = normalized_partitions
					# result_dict[disk]['partitions'] = create_gaps(normalized_partitions, disk, GLOBAL_BLOCK_MAP[disk]['size'])
				else:
					# TODO reconcilie list.
					# NO overlap. Fist delete then add/compare from the physical list
					# result_dict[disk]['partitions'] = create_gaps(normalized_partitions, disk, GLOBAL_BLOCK_MAP[disk]['size'])
					result_dict[disk]['partitions'] = normalized_partitions
	return result_dict

def from_general_dict_to_display(layout):

	entry_list = {}
	for entry in layout:
		entry_list[entry] = {key:value for key,value in layout[entry].items() if key != 'partitions'}
		entry_list[entry]['class'] = 'disk'
		for i,part in enumerate(layout[entry].get('partitions',{})):
			clave = part['id']
			entry_list[clave] = {key:value for key,value in part.items()}
			if not entry_list[clave].get('class'):
				entry_list[clave]['class'] = 'partition'
			entry_list[clave]['parent'] = entry
	return entry_list

def device_size_sectors(path):
	nombre = path.split('/')[-1]
	filename = f"/sys/class/block/{nombre}/size"
	with open(filename,'r') as file:
		size = file.read()
	return int(size) - 33 # The last 34 sectors are used by the system in GPT drives. If I substract 34 i miss 1 sector

def device_sector_size(path):
	nombre = path.split('/')[-1]
	filename = f"/sys/class/block/{nombre}/queue/logical_block_size"
	with open(filename,'r') as file:
		size = file.read()
	return int(size)

def eval_percent(percentage,start,end,disk_path):
	"""
	Routine to evaluate percentages of space allocation
	The input percentage will be from the gap space
	It outputs the space in sectors to be allocated (the integer part of the percentage)
	The output percentage will be from the start of the gap to the end of the disk, so a replay should give the same
	space allocations (plus minus a 1% of the disk)
	"""
	# TODO check if assumption is correct
	# TODO check off by one
	end_disk_sector = device_size_sectors(disk_path) - 1
	factor = float(percentage[:-1]) * 0.01  # assume it has been checked
	change_needed = True
	if end >= end_disk_sector:
		change_needed = False
		end = end_disk_sector
	sectors_allocated = int(round((end - start + 1) * factor,0))
	if change_needed:
		general_pct = f"{int(round(sectors_allocated * 100 / (end_disk_sector - start +1),0))}%"
	else:
		general_pct = percentage
	return sectors_allocated,general_pct

def from_global_to_partial_pct(percentage,start,size,disk_path):
	blocks_allocated = int(round((device_size_sectors(disk_path) - start) * float(percentage[:-1]) * 0.01,0))
	return f"{int(round(blocks_allocated * 100 / size,0))}%"

def convert_to_disk_layout(list_layout :dict) -> dict:
	""" This routine converts the abstract internal layout into a standard disk layout """
	# TODO set size to current configuration
	# TODO clear empty iterators ¿?
	def emount(value):
		""" has mountpoint """
		if value.get('mountpoint'):
			return True
		for subvolume in value.get('btrfs',{}).get('subvolumes',[]):  # expect normalized contents
			if subvolume.mountpoint:
				return True
		# TODO if i reuse a btrfs volume. How I do it

	disk_attr = ('wipe',)
	part_attr = ('boot','subvolumes', 'encrypted','filesystem','mountpoint','size','sizeG','start','wipe')
	disks = [key for key in list_layout if list_layout[key]['class'] == 'disk']
	disk_layout = {}
	for disk in disks:
		in_set = False
		if list_layout[disk].get('wipe'):
			in_set = True
		parts = [{key:data for key,data in value.items() if key in part_attr}
			for value in list_layout.values()
			if value['class'] == 'partition' and value.get('parent') == disk and (value.get('wipe') or emount(value))]
		if len(parts) > 0:
			in_set = True

		if in_set:
			disk_dict = {}
			for attr in disk_attr:
				disk_dict[attr] = list_layout[disk].get(attr)
			disk_dict['partitions'] = parts
			for part in disk_dict['partitions']:
				if 'subvolumes' in part:
					if part['subvolumes']:
						part['btrfs'] = {}
						part['btrfs']['subvolumes'] = part['subvolumes']
					del part['subvolumes']
				# size according to actual standard (not size but last entry
				end = int(part['size']) + int(part['start']) - 1
				part['start'] = f"{part['start']}s"
				part['size'] = f"{int(end)}s"
				# we create a sizeG argument, now just for show
				if part.get('sizeG'):
					if part['sizeG'].endswith('%'):
						pass
					else:
						result = re.split(r'(\d+\.\d+|\d+)',part['sizeG'].replace(',','').strip())
						if result[2]:
							part['sizeG'] = f"{convert_units(part['size'],result[2],'s')}{result[2]}"
						else:
							del part['sizeG']

			# TODO clean parts
			disk_layout.update({disk : disk_dict})
	return disk_layout

def location_to_gap(location :dict, text :str = '') -> list:
	gap = [int(location.get('start')),int(location.get('size') + location.get('start') - 1),location.get('size'),text]
	return gap

def gap_to_location(gap :list) -> dict:
	location = {'start':gap[0],
				'size':gap[2] if gap[2] else gap[1] - gap[0] + 1}
	return location

def merge_list(free,prev_line):
	# TODO convert prev as parameter as a list
	# we will include the selected chunck as free space, so we can expand it if necessary
	free.append(prev_line)
	free.sort()
	pos = free.index(prev_line)
	# the comparations should be equal, but this way i solve possible errors
	# read conditional as start_of_one_gap <= end_of_other_gap + 1 thus they are contiguous or overlap
	# must be in this order, to avoid errors in position, due to del
	if pos + 1 < len(free) and free[pos + 1][0] <= free[pos][1] + 1: # expand forward
		free[pos][1] = free[pos + 1][1]
		free[pos][2] = free[pos][1] - free[pos][0] + 1
		del free[pos + 1]
	if pos - 1 >= 0 and free[pos][0] <= free[pos - 1][1] + 1: # expand backwards
		free[pos][0] = free[pos - 1][0]
		free[pos][2] = free[pos][1] - free[pos][0] + 1
		del free[pos - 1]

def align_entry(entry,ALIGNMENT,LAST_SECTOR):
	normalized = entry[:]
	if ALIGNMENT > 1:
		# print(">{:>20,}{:>20,}{:>20,} {}".format(*slot))
		if entry[0] % ALIGNMENT != 0:
			pos_ini = (entry[0] // ALIGNMENT + 1) * ALIGNMENT
			if pos_ini > LAST_SECTOR:
				pos_ini = LAST_SECTOR
		else:
			pos_ini = entry[0]
		if entry[1] % ALIGNMENT != 0:
			pos_fin = (entry[1] // ALIGNMENT) * ALIGNMENT - 1
		else:
			pos_fin = entry[0]
		size = pos_fin - pos_ini + 1
		normalized[0] = pos_ini
		normalized[1] = pos_fin
		normalized[2] = size
	return normalized


"""
UI classes
"""

class PartitionMenu(archinstall.GeneralMenu):
	def __init__(self,parameters,block_device,caller=None):
		self.caller = caller
		if isinstance(block_device,archinstall.BlockDevice):
			self.block_device = block_device
		else:
			self.block_device = archinstall.BlockDevice(block_device) # TODO suspect lots of checks
		self.data = parameters
		self.ds = deepcopy(self.data)
		# we convert formats
		if 'start' in self.ds or 'size' in self.ds:
			self.ds['location'] = {'start':self.ds.get('start'), 'size':self.ds.get('size'), 'sizeG':self.ds.get('sizeG')}
			del self.ds['start']
			del self.ds['size']
		if 'filesystem' in self.ds:
			self.ds['fs'] = self.ds['filesystem'].get('format')
			self.ds['fs_fmt_options'] = ','.join(self.ds['filesystem'].get('format_options',[]))
			self.ds['fs_mnt_options'] = ','.join(self.ds['filesystem'].get('mount_options',[]))
			del self.ds['filesystem']
		# temporary
		if 'type' not in self.ds:
			self.ds['type'] = 'primary'
		super().__init__(data_store=self.ds)

	def _setup_selection_menu_options(self):
		self._menu_options['location'] = archinstall.Selector(str(_("Physical layout")),
									self._select_physical,
									display_func=self._show_location,
									enabled=True)
		self._menu_options['type'] = archinstall.Selector(str(_("Partition type")),
							enabled=False)
		# TODO ensure unicity
		self._menu_options['mountpoint'] = archinstall.Selector(str(_("Mount Point")),
							lambda prev: self._generic_string_editor(str(_('Edit Mount Point :')),prev),

							dependencies=['fs'],enabled=True)
		self._menu_options['fs'] = archinstall.Selector(str(_("File System Type")),
							self._select_filesystem,
							enabled=True)
		self._menu_options['fs_fmt_options'] = archinstall.Selector(str(_("File System Format Options")),
							lambda prev: self._generic_string_editor(str(_('Edit format options :')),prev),
							dependencies=['fs'],enabled=True)
		self._menu_options['fs_mnt_options'] = archinstall.Selector(str(_("File System Mount Options")),
							lambda prev: self._generic_string_editor(str(_('Edit mount options :')),prev),
							dependencies=['fs'],enabled=True)
		self._menu_options['subvolumes'] = archinstall.Selector(str(_("Btrfs Subvolumes")),
							self._manage_subvolumes,
							dependencies=['fs'],
							enabled=True if self.ds.get('fs') == 'btrfs' else False) # TODO only if it is btrfs
		self._menu_options['boot'] = archinstall.Selector(str(_("Is bootable")),
							self._select_boot,
							enabled=True)
		self._menu_options['encrypted'] = archinstall.Selector(str(_("Encrypted")),
							lambda prev: self._generic_boolean_editor(str(_('Set ENCRYPTED partition :')),prev),
							enabled=True)
		# readonly options
		if self.ds.get('uuid'):
			self._menu_options['actual_mountpoint'] = archinstall.Selector(str(_("Actual mount")),
								enabled=True)
			if self.ds.get('fs') == 'btrfs':
				self._menu_options['actual_subvolumes'] = archinstall.Selector(str(_("Actual Btrfs Subvolumes")),
									enabled=True)
			self._menu_options['uuid'] = archinstall.Selector(str(_("uuid")),
								enabled=True)

		self._menu_options['save'] = archinstall.Selector(str(_('Save')),
													exec_func=lambda n,v:True,
													enabled=True)
		self._menu_options['cancel'] = archinstall.Selector(str(_('Cancel')),
													func=lambda pre:True,
													exec_func=lambda n,v:self.fast_exit(n),
													enabled=True)
		self.cancel_action = 'cancel'
		self.save_action = 'save'
		self.bottom_list = [self.save_action,self.cancel_action]

	def fast_exit(self,accion):
		if self.option(accion).get_selection():
			for item in self.list_options():
				if self.option(item).is_mandatory():
					self.option(item).set_mandatory(False)
		return True

	def exit_callback(self):
		# we exit without moving data
		if self.option(self.cancel_action).get_selection():
			return
		# if no location is given we abort
		if self.ds.get('location') is None:
			return
		for item in self.ds:
			# reconvert to basic format
			if item == 'location':
				self.data['start'] = self.ds[item].get('start')
				self.data['size'] = self.ds[item].get('size')
				self.data['sizeG'] = self.ds[item].get('sizeG')
			elif item == 'fs' and self.ds.get(item):
				self.data['filesystem'] = {}
				self.data['filesystem']['format'] = self.ds[item]
			elif item == 'fs_fmt_options' and self.ds.get(item):
				self.data['filesystem']['format_options'] = self.ds[item].split(',')
			elif item == 'fs_mnt_options' and self.ds.get(item):
				self.data['filesystem']['mount_options'] = self.ds[item].split(',')
			elif item not in self.bottom_list:
				self.data[item] = self.ds[item]

	def _generic_string_editor(self,prompt,prev):
		return archinstall.TextInput(prompt,prev).run()

	def _generic_boolean_editor(self,prompt,prev):
		if prev:
			base_value = 'yes'
		else:
			base_value = 'no'
		response = archinstall.Menu(prompt,['yes','no'], preset_values=base_value).run()
		if response.value == 'yes':
			return True
		else:
			return False

	def _show_location(self,location):
		if location.get('sizeG'):
			return f"{location['sizeG']} : {int(location['size'])} sectors starting at {int(location['start'])}"
		else:
			return f"{int(location['size'])} sectors  starting at {int(location['start'])} ({convert_units(location['size'],'GiB','s')} GiB)"

	def _select_boot(self,prev):
		value = self._generic_boolean_editor(str(_('Set bootable partition :')),prev),
		# TODO needs a refresh
		# TODO only a boot per disk ¿?
		# TODO It's a bit more complex than that. This is only for GPT drives
		if value[0]:
			self.ds['mountpoint'] = '/boot'
			self.ds['fs'] = 'FAT32'
			self.ds['encrypted'] = False
		return value[0]

	def _select_filesystem(self,prev):
		fstype_title = _('Enter a desired filesystem type for the partition: ')
		fstype = archinstall.Menu(fstype_title, archinstall.fs_types(), skip=False, preset_values=prev).run()
		if fstype.value != self.data.get('filesystem',{}).get('format') and self.data.get('uuid'): # changed FS means reformat if the disk exists
			self.ds['wipe'] = True
		if fstype.value == 'btrfs':
			self.option('subvolumes').set_enabled(True)
		else:
			self.option('subvolumes').set_enabled(False)
		return fstype.value

	def _select_physical(self,prev):
		# TODO check if IDs have to change when you modify a partition, and if it is allowed
		from os import system
		if self.data.get('uuid'): # an existing partition can not be physically changed
			return prev
		if not prev:
			prev = {}
		# we get the free list and if there exists prev we add this to the list
		if self.caller:
			total_size,sector_size,free = self.caller.gap_map(self.block_device)
		else: # Might not be needed, but permits to execute standalone
			total_size,sector_size,free = list_free_space(self.block_device,'s')
			total_size = int(total_size[:-1])

		ALIGNMENT = convert_units(archinstall.arguments.get('align',0),'s','s') # 2**13
		MIN_PARTITION = ALIGNMENT if ALIGNMENT > 1 else 2**13 # 4 MiB
		LAST_SECTOR = total_size - 33 # last assignable sector (we leave 34 sectors por internal info

		def align_gaps(free_slots,ALIGNMENT,MIN_PARTITIONS,LAST_SECTOR):
			#
			# the gap list has to be renormalized thru the use of ALIGNMENT,
			# so we only asign aligned partitions to the structure we define
			#
			norm_free_slot = []
			for slot in free_slots:
				norm_slot = align_entry(slot,ALIGNMENT,LAST_SECTOR)
				if norm_slot[2] > 0:
					norm_free_slot.append(norm_slot)
				else:
					continue
				# mark unavailable slots
				if len(norm_free_slot[-1]) == 3:
					norm_free_slot[-1].append('')
				if norm_free_slot[-1][2] < MIN_PARTITION:
					norm_free_slot[-1][3] += ' too short'
			return norm_free_slot

		def show_free_slots(free,prev,ALIGNMENT):
			# print("<{:>20,}{:>20,}{:>20,} {}".format(*norm_free_slot[-1]))
			print()
			print(f"List of free space at {self.block_device.path} in sectors")
			print()
			print("{:20} | {:20} | {:20}".format('start','end','size'))
			print("{}|{}|{}".format('-' * 21,'-' * 21,'-' * 21))
			for linea in free:
				if len(linea) == 3:
					print(f"{linea[0]:>20,} | {linea[1]:>20,} | {unit_best_fit(linea[2]):>12}")
				else:
					print(f"{linea[0]:>20,} | {linea[1]:>20,} | {unit_best_fit(linea[2]):>12}    {linea[3]}")
			print()
			# TODO check minimal size
			# TODO text with possible unit definition
			# TODO preselect optimal ¿? hole
			if prev:
				print(_("Current physical location selection"))
				print(f"{int(prev.get('start')):>20,} | {int(prev.get('size') + prev.get('start') -1):>20,} | {unit_best_fit(prev.get('size')):>12}")
				if ALIGNMENT > 1:
					print(_("Current physical location selection; aligned"))
					norm_slot = align_entry([int(prev.get('start')),int(prev.get('size')) + int(prev.get('start')) - 1,int(prev.get('size'))],ALIGNMENT,LAST_SECTOR)
					print(f"{norm_slot[0]:>20,} | {norm_slot[1]:>20,} | {unit_best_fit(norm_slot[2]):>12}")
			print()

		# we will include the selected chunck as free space, so we can expand it if necessary
		if prev:
			merge_list(free,location_to_gap(prev,'Current Location'))
		# normalize free space according to alignment
		free = align_gaps(free,ALIGNMENT,MIN_PARTITION,LAST_SECTOR)

		if prev:
			current_gap = [line[3] if len(line) == 4 else None for line in free].index('Current Location')
		else:
			current_gap = 0
		# TODO define a minimal start position
		# TODO standarize units for return code
		system('clear')
		show_free_slots(free,prev,ALIGNMENT)

		starts = str(int(prev.get('start'))) if prev.get('start') else ''
		if prev.get('sizeG'):
			# TODO percentages back
			if prev['sizeG'].strip()[-1] == '%':
				size = from_global_to_partial_pct(prev['sizeG'],prev['start'],free[current_gap][1] - prev['start'] + 1,self.block_device.path)
			else:
				size = f"{prev.get('sizeG')}"
		else:
			size = f"{prev.get('size')}" if prev.get('size') else ''
		while True:
			if prev:
				prompt = _("Define a start sector for the partition. Enter a value or \n"
						"c to get the first sector of the current slot \n"
						"q to quit \n"
						"==> ")
			else:
				prompt = _("Define a start sector for the partition. Enter a value or \n"
						"f to get the first sector of the first free slot which can hold a partition\n"
						"l to get the first sector of the last free slot \n"
						"q to quit \n"
						"==> ")
			starts = archinstall.TextInput(prompt,starts).run()
			inplace = False
			if starts.lower() == 'q':
				if prev:
					return prev
				else:
					return None
			elif starts.lower() == 'f':
				# TODO check really which is the first allocatable sector in a disk
				starts = free[0][0]
			elif starts.lower() == 'l':
				starts = free[-1][0]
			elif starts.lower() == 'c':
				starts = free[current_gap][0]
			else:
				starts = int(convert_units(starts,'s','s')) # default value are sectors
			maxsize = 0
			endgap = 0
			for gap in free:
				# asume it is always sectors
				if int(gap[0]) <= int(starts) <= int(gap[1]):
					endgap = int(gap[1])
					maxsize = int(gap[1]) - starts + 1 # i think i got it right
					maxsize_g = convert_units(f"{maxsize}s",'GiB')
					inplace = True
					break
			if not inplace:
				print(_("Selected sector {} outside an empty gap").format(starts))
			else:
				break
		while True:
			size = archinstall.TextInput(_("Define a size for the partition \n(max {} sectors / {}GiB), a percentaje of the free space (ends with %),\n or q to quit \n ==> ").format(maxsize,maxsize_g),size).run()
			if size.lower() == 'q':
				if prev:
					return prev
				else:
					return None
			if size.endswith('%'):
				size_s,size = eval_percent(size,starts,endgap,self.block_device.path)
			else:
				size_s = convert_units(size,'s','s')
			# TODO when they match something fails ¿? decimals ?
			if size_s > maxsize:
				print(f"Size is too big for selected  gap. {size_s} > {maxsize} Reduce it to fit")
			else: # TODO
				break
		if size.lower().strip()[-1] in ('b','%'):
			return {'start':starts,'size':size_s,'sizeG':size}
		else:
			return {'start':starts,'size':size_s}

	def _manage_subvolumes(self,prev):
		if self.option('fs').get_selection() != 'btrfs':
			return []
		# TODO partition reference if possible
		# band-aid
		if prev is None:
			prev = []
		return SubvolumeList(_("Manage btrfs subvolumes for current partition"),prev).run()

# BAND-AID
# self.data -> self._data
# TODO
#    * ripple_delete
#    * gap_map
#    reorder_data
#    action list -> filter_option
class DevList(archinstall.ListManager):
	def __init__(self,prompt,data_list):
		self.ObjectActions = [
			'Add disk to installation set',          # 0
			'Add partition',                         # 1
			'Clear disk (delete disk contents)',     # 2
			'Clear Partition & edit attributes',     # 3
			'Edit partition attributes',             # 4
			'Exclude disk from installation set',    # 5
			'Exclude partition from installation set', # 6
			'Delete partition'                       # 7
		]
		self.ObjectNullAction = None
		self.ObjectDefaultAction = 'Reset'
		self.partitions_to_delete = {}
		super().__init__(prompt,data_list,[self.ObjectDefaultAction],self.ObjectActions)

	def run(self):
		result_list = super().run()
		# TODO there is no self.action by now
		if self.last_choice.value != self._confirm_action:
			self.partitions_to_delete = {}
		return result_list, self.partitions_to_delete

	def selected_action_display(self, selection: Any) -> str:
		# this will return the value to be displayed in the
		# "Select an action for '{}'" string
		print(selection)
		if self._data[selection]['class'] == 'disk':
			text = 'Volume {}'.format(selection)
		else:
			text = 'slot {}, type {}'.format(selection,self._data[selection]['class'])
		return text

	def reformat(self, data: List[Any]) -> Dict[str, Any]:
		# this should return a dictionary of display string to actual data entry
		# mapping; if the value for a given display string is None it will be used
		# in the header value (useful when displaying tables)
		raw_result = self._header() | {self._prettify(key,value):key for key,value in data.items()}
		return raw_result

	def handle_action(self, action: Any, entry: Optional[Any], data: List[Any]) -> List[Any]:
		# this function is called when a base action or
		# a specific action for an entry is triggered
		# final sort has to be done here
		return self._sort_data(self._exec_action(action,entry,data))
		raise NotImplementedError('Please implement me in the child class')

	def filter_options(self, selection :Any, options :List[str]) -> List[str]:
		# filter which actions to show for an specific selection
		target = self._data[selection]
		disk_actions = (0,1,2,5)
		part_actions = (3,4,7)  # BUG hide partition disallowed for the time being (3,4,6,7)
		if target.get('class') == 'disk':
			return [options[i] for i in disk_actions]
		elif target.get('class') == 'gap':
			return [options[1]]
		elif target.get('class') == 'partition':
			return [options[i] for i in part_actions]
		else:
			return options
		# ... if you need some changes to the action list based on self.target

		return options

	def _header(self):
		bar = r'|'
		if archinstall.arguments.get('long_form'):
			header = ((f"  {'identifier':^16}"
						f"{bar}{'wipe':^5}"
						f"{bar}{'boot':^5}"
						f"{bar}{'encrypted':^7.7}"
						f"{bar}{'start':^12}"
						f"{bar}{'size (sectors def.)':^12.12} "
						f"{bar}{'filesystem':^12}"
						f"{bar}{'mount at':^19}"
						f"{bar}{'currently mounted':^19}"
						f"{bar}{'uuid':^24}"),
						f"{'-' * 18}{bar}{'-'*5}{bar}{'-'*5}{bar}{'-'*7}{bar}{'-'*12}{bar}{'-'*13}{bar}{'-'*12}{bar}{'-'*19}{bar}{'-'*19}{bar}{'-'*24}")
		else:
			header = ((f"  {'identifier':^16}"
						f"{bar}{'wipe':^5}"
						f"{bar}{'boot':^5}"
						f"{bar}{'encrypted':^7.7}"
						f"{bar}{'s. (GiB)':^8.8} "
						f"{bar}{'fs':^8}"
						f"{bar}{'mount at':^19}"
						f"{bar}{'used':^6}"),
						f"{'-' * 18}{bar}{'-'*5}{bar}{'-'*5}{bar}{'-'*7}{bar}{'-'*9}{bar}{'-'*8}{bar}{'-'*19}{bar}{'-'*6}")
		return {"  " + head:None for head in header}

	def _prettify(self,entry_key,entry):
		blank = ''
		bar = r'\|'

		def pretty_disk(entry_key,entry):
			# TODO from disk_layout it misses size,
			# TODO both miss free storage
			if archinstall.arguments.get('long_form'):
				return (f"{entry_key:18}"
						f"{bar}{'WIPE' if entry.get('wipe') else blank:^5}"
						f"{bar}{blank:^5}"
						f"{bar}{blank:^7}"
						f"{bar}{blank:^12}"
						f"{bar}{int(entry['size']) if entry.get('size') else 0 :<12,}")
			else:
				return (f"{entry_key:18}"
						f"{bar}{'WIPE' if entry.get('wipe') else blank:^5}"
						f"{bar}{blank:^5}"
						f"{bar}{blank:^7}"
						f"{bar}{convert_units(entry['size'],'GiB','s') if entry.get('size') else 0.0 :<8,.1f}")

		def pretty_part(entry_key,entry):
			# TODO normalize size
			# TODO normalize start
			# TODO get actual_mountpoint
			if entry.get('mountpoint'):
				mount = f"{entry['mountpoint']}"
			elif entry.get('subvolumes'):
				subvolumes = entry['subvolumes']
				mountlist = []
				for subvol in subvolumes:
					# band aid
					if isinstance(subvol,archinstall.Subvolume) and subvol.mountpoint:
						mountlist.append(subvol.mountpoint)
				if mountlist:
					mount = f"{', '.join(mountlist):15.15}..."
				else:
					mount = blank
			else:
				mount = blank

			amount = self.amount(entry)

			# UUID for manual layout
			if entry.get('path'):
				identifier = entry['path']
			elif entry['class'] == 'gap':
				identifier = blank
			else:
				identifier = ' (new)'
			if archinstall.arguments.get('long_form',False):
				return (f"  └─{identifier:14}"
						f"{bar}{'WIPE' if entry.get('wipe') else blank:^5}"
						f"{bar}{'BOOT' if entry.get('boot') else blank:^5}"
						f"{bar}{'CRYPT' if entry.get('encrypted') else blank:^7}"
						f"{bar}{entry['start'] if entry.get('start') else 0 :>12}"
						f"{bar}{entry['sizeG'] if entry.get('sizeG') else entry.get('size'):>12} "
						f"{bar}{entry['filesystem'].get('format') if entry.get('filesystem') else blank:12}"
						f"{bar}{mount:19.19}"
						f"{bar}{amount:19.19}"
						f"{bar}{entry['uuid'] if entry.get('uuid') else blank} ")
			else:
				return (f"  └─{identifier:14}"                                                               # 16
						f"{bar}{'WIPE' if entry.get('wipe') else blank:^5}"                                # 22
						f"{bar}{'BOOT' if entry.get('boot') else blank:^5}"                                # 28
						f"{bar}{'CRYPT' if entry.get('encrypted') else blank:^7}"                          # 36
						f"{bar}{convert_units(entry.get('size',0),'GiB','s'):>8} "                     # 45
						f"{bar}{entry['filesystem'].get('format') if entry.get('filesystem') else blank:8.8}"# 54
						f"{bar}{mount:19.19}"                                                              # 74
						f"{bar}{'IN USE' if amount or entry.get('uuid') else blank:6}")

		if entry['class'] == 'disk':
			return pretty_disk(entry_key,entry)
		else:
			return pretty_part(entry_key,entry)

	def amount(self,entry):
		blank = ''
		if entry.get('actual_subvolumes'):
			subvolumes = entry['actual_subvolumes']
			mountlist = []
			for subvol in subvolumes:
				mountlist.append(subvol.mountpoint)
			if mountlist:
				amount = f"//HOST({', '.join(mountlist):15.15})..."
			else:
				amount = blank
		elif entry.get('actual_mountpoint'):
			amount = f"//HOST{entry['actual_mountpoint']}"
		else:
			amount = blank
		return amount

	def _exec_action(self,action,entry,data):
		if entry:
			key = entry
			value = data[entry]
			if value.get('class') == 'disk':
				disk = key
			else:
				disk = value.get('parent')
		else:
			key = None
			value = None
			disk = None
		# reset
		if action == self.ObjectDefaultAction:
			return self._action_reset(key,value,disk,data)
		# Add disk to installation set',          # 0
		elif action == self.ObjectActions[0]:
			# select harddrive still not on set
			# load its info and partitions into the list
			return self._action_not_implemeted(key,value,disk,data)
		# Add partition',                         # 1
		elif action == self.ObjectActions[1]:
			return self._action_add_partition(key,value,disk,data)
		# Clear disk (delete disk contents)',     # 2
		elif action == self.ObjectActions[2]:
			return self._action_clear_disk(key,value,disk,data)
		# Clear Partition & edit attributes',     # 3
		elif action == self.ObjectActions[3]:
			return self._action_clear_partition(key,value,disk,data)
		# Edit partition attributes',             # 4
		elif action == self.ObjectActions[4]:
			return self._action_edit_partition(key,value,disk,data)
		# Exclude disk from installation set',    # 5
		elif action == self.ObjectActions[5]:
			return self._action_exclude_disk(key,value,disk,data)
		# Exclude partition from installation set', # 6
		elif action == self.ObjectActions[6]:
			# BUG for the time being disallowed. Current implementation is faulty
			return self._action_not_implemeted(key,value,disk,data)
		# Delete partition'                       # 7
		elif action == self.ObjectActions[7]:
			return self._action_delete_partition(key,value,disk,data)
		return data

	def _action_not_implemeted(self,key,value,disk,data):
		archinstall.log('Action still not implemented')
		return data

	def _action_reset(self,key,value,disk,data):
		self.partitions_to_delete = {}
		return self._original_data

	def _action_add_partition(self,key,value,disk,data):
		# check if empty disk. A bit complex now. TODO sumplify
		if len([key for key in data if key.startswith(disk) and data[key]['class'] == 'partition']) == 0:
			is_empty_disk = True
		else:
			is_empty_disk = False
		part_data = {}
		if value.get('class') == 'gap':
			part_data['start'] = value.get('start')
			part_data['size'] = value.get('size')

		with PartitionMenu(part_data,disk,self) as add_menu:
			exit_menu = False
			for option in add_menu.list_options():
				if option in ('location','mountpoint','fs','subvolumes','boot','encrypted'):
					add_menu.synch(option)
					add_menu.exec_option(option)
					# broke execution there
					if option == 'location' and add_menu.option('location').get_selection() is None:
						exit_menu = True
						break
			if not exit_menu:
				add_menu.run()
			else:
				add_menu.exec_option(add_menu.cancel_action)

		if part_data:
			key = f"{disk} {part_data.get('start'):>15}"
			part_data['id'] = key
			part_data['class'] = 'partition'
			part_data['type'] = 'primary'
			part_data['wipe'] = True
			part_data['parent'] = disk
			data.update({key:part_data})
			if is_empty_disk:
				data[disk]['wipe'] = True
			# TODO size comes in strange format
		return data

	def _action_clear_disk(self,key,value,disk,data):
		data[key]['wipe'] = True
		# no need to delete partitions in this disk
		self.ripple_delete(key,head=False)
		return data

	def _action_clear_partition(self,key,value,disk,data):
		PartitionMenu(value,disk,self).run()
		if value:
			value['wipe'] = True
			data.update({key:value})
		return data

	def _action_edit_partition(self,key,value,disk,data):
		PartitionMenu(value,disk,self).run()
		data.update({key:value})
		return data

	def _action_exclude_disk(self,key,value,disk,data):
		self.ripple_delete(key,head=True)
		return data

	def _action_delete_partition(self,key,value,disk,data):
		if self.amount(value):
			print('Can not delete partition, because it is in use')  # TODO it doesn't show actually
			return
		elif value.get('uuid'):
			self.partitions_to_delete.update({key:value})
		del data[key]
		return data

	def ripple_delete(self,key,head):
		keys = list(self._data.keys())
		for entry in keys:
			if entry == key and not head:
				continue
			if entry.startswith(key):
				del self._data[entry]
		keys = list(self.partitions_to_delete.keys())
		for entry in keys:
			if entry.startswith(key):
				del self.partitions_to_delete[entry]
		# placeholder

	def gap_map(self,block_device):
		gap_list = []
		if isinstance(block_device,archinstall.BlockDevice):
			disk = block_device.path
		else:
			disk = block_device
		tmp_gaps = [value for part,value in sorted(self._data.items()) if value.get('parent') == disk and value['class'] == 'gap']
		for gap in tmp_gaps:
			# and the off by one ¿?
			gap_list.append([gap['start'],gap['size'] + gap['start'] - 1 ,gap['size']])
		# the return values are meant to be compatible with list_free_space.
		return GLOBAL_BLOCK_MAP[disk]['size'],GLOBAL_BLOCK_MAP[disk]['sector_size'],gap_list

	def _sort_data(self,data):
		new_struct = {}
		tmp_disks = [disk for disk in sorted(list(data.keys())) if data[disk].get('class') == 'disk']
		for disk in tmp_disks:
			new_struct.update({disk:data[disk]})
			tmp_parts = [value for part,value in sorted(data.items()) if value.get('parent') == disk and value['class'] == 'partition']
			new_parts = create_gaps(tmp_parts,disk,GLOBAL_BLOCK_MAP[disk]['size'])
			new_struct[disk]['partitions'] = new_parts
		return from_general_dict_to_display(new_struct)


"""
Navigator
"""

def frontpage():
	create_global_block_map()
	arguments = archinstall.arguments
	storage = archinstall.storage
	layout = {}
	if arguments.get('disk_layouts'):
		# TODO check if disks still exist
		# TODO fill missing arguments re physical layout
		layout = arguments.get('disk_layouts')
		harddrives = [archinstall.BlockDevice(key) for key in layout]
		return from_general_dict_to_display(integrate_layout_in_global_map(harddrives,layout))
	else:
		prompt = '*** Disk Management ***'
		options = [
			"Use whatever is defined at {} as the instalation target".format(storage['MOUNT_POINT']),
			'Select full disk(s), delete its contents and use a suggested layout',
			'Select disk(s) and manually manage them',
			'View full disk structure'
		]
		result = archinstall.Menu(prompt,options,skip=True,sort=False).run()
		if result:
			# BAND-AID
			harddrives = []
			if result.value == options[0]:
				# TODO should we check if the directory exists as a mountpoint ?
				arguments['harddrives'] = []
				if 'disk_layout' in arguments:
					del arguments['disk_layout']
				return "direct" # patch, odious patch
			elif result.value in (options[1],options[2]):
				old_harddrives = arguments.get('harddrives', [])
				harddrives = archinstall.select_harddrives(old_harddrives)
				if not harddrives:
					return # TODO ought to be return to the menu
				arguments['harddrives'] = harddrives
				# in case the harddrives got changed we have to reset the disk layout as well
				# TODO is that needed now ?
				if old_harddrives != harddrives:
					arguments['disk_layouts'] = {}
				if result.value == options[1]:
					# we will create an standard layout, but will left open, editing it
					layout = get_default_partition_layout(harddrives) # TODO advanced options
				# elif result == options[2]:
					# layout = navigate_structure(arguments['harddrives'])
			elif result.value == options[3]:
				harddrives = []
				# layout = navigate_structure()
			else:
				pass
			return from_general_dict_to_display(integrate_layout_in_global_map(harddrives,layout))
		else:
			return

def perform_installation(mountpoint):
	"""
		Issue a final warning before we continue with something un-revertable.
		We mention the drive one last time, and count from 5 to 0.
	"""
	if archinstall.arguments.get('harddrives', None) or archinstall.arguments.get('partitions_to_delete',None):
		print(f" ! Formatting {archinstall.arguments['harddrives']} in ", end='')
		archinstall.do_countdown()
		"""
			Setup the blockdevice, filesystem (and optionally encryption).
			Once that's done, we'll hand over to perform_installation()
		"""
		mode = archinstall.GPT
		if archinstall.has_uefi() is False:
			mode = archinstall.MBR

		for part_to_delete in archinstall.arguments.get('partitions_to_delete',[]):
			delete_partition(mode,*part_to_delete)
		if not archinstall.arguments.get('harddrives',None):
			return
		for drive in archinstall.arguments.get('harddrives', []):
			if archinstall.arguments.get('disk_layouts', {}).get(drive.path):
				with archinstall.Filesystem(drive, mode) as fs:
					fs.load_layout(archinstall.arguments['disk_layouts'][drive.path])

	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	with archinstall.Installer(mountpoint, kernels=None) as installation:
		# Mount all the drives to the desired mountpoint
		# This *can* be done outside of the installation, but the installer can deal with it.
		if archinstall.arguments.get('disk_layouts'):
			installation.mount_ordered_layout(archinstall.arguments['disk_layouts'])

		# Placing /boot check during installation because this will catch both re-use and wipe scenarios.
		for partition in installation.partitions:
			if partition.mountpoint == installation.target + '/boot':
				if partition.size <= 0.25: # in GB
					raise archinstall.DiskError(f"The selected /boot partition in use is not large enough to properly install a boot loader. Please resize it to at least 256MB and re-run the installation.")
		# to generate a fstab directory holder. Avoids an error on exit and at the same time checks the procedure
		target = pathlib.Path(f"{mountpoint}/etc/fstab")
		if not target.parent.exists():
			target.parent.mkdir(parents=True)

	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	archinstall.log(f"Disk states after installing: {archinstall.disk_layouts()}", level=logging.DEBUG)

def log_execution_environment():
	# Log various information about hardware before starting the installation. This might assist in troubleshooting
	archinstall.log(f"Hardware model detected: {archinstall.sys_vendor()} {archinstall.product_name()}; UEFI mode: {archinstall.has_uefi()}", level=logging.DEBUG)
	archinstall.log(f"Processor model detected: {archinstall.cpu_model()}", level=logging.DEBUG)
	archinstall.log(f"Memory statistics: {archinstall.mem_available()} available out of {archinstall.mem_total()} total installed", level=logging.DEBUG)
	archinstall.log(f"Virtualization detected: {archinstall.virtualization()}; is VM: {archinstall.is_vm()}", level=logging.DEBUG)
	archinstall.log(f"Graphics devices detected: {archinstall.graphics_devices().keys()}", level=logging.DEBUG)

	# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
	archinstall.log(f"Disk states before installing: {archinstall.disk_layouts()}", level=logging.DEBUG)

def ask_user_questions():
	"""
		First, we'll ask the user for a bunch of user input.
		Not until we're satisfied with what we want to install
		will we continue with the actual installation steps.
	"""
	def perform_disk_management():
		list_layout = frontpage()
		if not list_layout:
			exit()
		if list_layout == "direct":
			exit()  # this routine does nothing in this case
		else:
			# pprint(list_layout)
			dl = DevList('*** Disk Layout ***',list_layout)
			result,partitions_to_delete = dl.run()
			if not result or dl.last_choice.value != dl._confirm_action:
				exit()
			archinstall.arguments['disk_layouts'] = convert_to_disk_layout(result)
			archinstall.arguments['harddrives'] = [archinstall.BlockDevice(key) for key in archinstall.arguments['disk_layouts']]
			archinstall.arguments['partitions_to_delete'] = [
				[partitions_to_delete[part]['parent'],
					partitions_to_delete[part]['uuid'],
					partitions_to_delete[part]['partnr']]
				for part in partitions_to_delete]
			if archinstall.arguments.get('harddrives'):
				manage_encryption()
	perform_disk_management()

def manage_encryption():
	# we do exactly as has been done till now. TODO I think this needs a lot more work
	if passwd := archinstall.get_password(prompt=str(_('Enter disk encryption password (leave blank for no encryption): '))):
		archinstall.arguments["!encryption-password"] = passwd
		# TODO check if it is already set. and if any action is needed
		if archinstall.arguments.get('harddrives', None):
			# If no partitions was marked as encrypted, but a password was supplied and we have some disks to format..
			# Then we need to identify which partitions to encrypt. This will default to / (root).
			if len(list(archinstall.encrypted_partitions(archinstall.arguments.get('disk_layouts', [])))) == 0:
				archinstall.arguments['disk_layouts'] = archinstall.select_encrypted_partitions(
					archinstall.arguments['disk_layouts'], archinstall.arguments['!encryption-password'])

def delete_partition(mode,disk,uuid,partnr):
	block = archinstall.Filesystem(archinstall.BlockDevice(disk),mode) # FIX needed only because parted is a method of FileSystem and needs a blockdevice
	part_cmd = f"{disk} rm {partnr}"
	if not block.parted(part_cmd):
		archinstall.log(f'Something went wrong with the partition delete for uuid {uuid} nr {partnr}',fg="red")
		exit(1)
	else:
		archinstall.log(f"Partition nr {partnr} from {disk} deleted")
	# possible error codes
	# partition does not exists
	# partition in use
	# others


if archinstall.arguments.get('help'):
	print("See `man archinstall` for help.")
	exit(0)
if os.getuid() != 0:
	print("Archinstall requires root privileges to run. See --help for more.")
	exit(1)

log_execution_environment()

if not archinstall.arguments.get('silent'):
	ask_user_questions()

config_output = archinstall.ConfigurationOutput(archinstall.arguments)
config_output._disk_layout_file = 'layout_diskmanager.json'
if not archinstall.arguments.get('silent'):
	config_output.show()
config_output.save()
# DEBUG exits always. Now it is so unstable
if archinstall.arguments.get('dry_run'):
	exit(0)
if not archinstall.arguments.get('silent'):
	input('Press Enter to continue.')

perform_installation(archinstall.storage.get('MOUNT_POINT', '/mnt'))
