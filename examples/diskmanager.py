import archinstall
import pathlib
from pprint import pprint
# from pudb import set_trace
import logging
from copy import deepcopy, copy
import re

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
				if device_info['TYPE'] == 'btrfs':
					subvol_info = {}
					for subvol in result[res].subvolumes:
						subvol_info[subvol.name] = {'mountpoint':subvol.target, 'options':None}
				else:
					subvol_info = {}
				partition = {
					"id": f"{result[res].parent} {device_info['PART_ENTRY_OFFSET']:>15}",
					"type" : device_info['PART_ENTRY_NAME'],
					"start" : device_info['PART_ENTRY_OFFSET'],
					"size" : device_info['PART_ENTRY_SIZE'],
					# "sizeG": round(int(device_info['PART_ENTRY_SIZE']) * 512 / archinstall.GIGA,1),
					"boot" : device_info['PART_ENTRY_NAME'] == 'EFI' or device_info.get('PART_ENTRY_TYPE','').startswith('c12a') or result[res].boot,
					"encrypted" : encrypted,
					"wipe" : False,
					"actual_mountpoint" : result[res].mountpoint,  # <-- this is false
					"mountpoint" : None,
					"filesystem" : {
						"format" : device_info['TYPE'] if device_info['TYPE'] != 'vfat' else device_info['VERSION']
					},
					"uuid": result[res].uuid,
					# "partnr": device_info['PART_ENTRY_NUMBER'],
					"path": device_info['PATH'],
					"actual_subvolumes": subvol_info,
					"subvolumes":{}
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
			print('==>')
			print(res)
			print(result[res])
			print('\t',result[res].name)
			print('\t',result[res].path)
			print('\t',result[res].MapperDev)
			print('\t\t',result[res].MapperDev.name)
			print('\t\t',result[res].MapperDev.partition)
			print('\t\t',result[res].MapperDev.path)
			print('\t\t',result[res].MapperDev.filesystem)
			print('\t\t',result[res].MapperDev.subvolumes)
			print('\t\t',result[res].MapperDev.mount_information)
			print('\t\t',result[res].MapperDev.mountpoint)
			print('\t',result[res].mountpoint)
			print('\t',result[res].filesystem)
			pprint(device_info)
			print()
			# TODO move relevant information to the corresponding partition
	for disk in disk_layout:
		if 'structure' in disk_layout[disk]:
			disk_layout[disk]['structure'] = create_gaps(disk_layout[disk]['structure'],disk,disk_layout[disk]['size'])
	GLOBAL_BLOCK_MAP.update(disk_layout)

def normalize_from_layout(partition_list,disk):
	last_sector = GLOBAL_BLOCK_MAP[disk]['size'] - 1

	def subvol_normalize(part):
		subvol_info = part.get('btrfs',{}).get('subvolumes',{})
		norm_subvol = {}
		if subvol_info:
			for subvol in subvol_info:
				if subvol_info[subvol] is None:
					norm_subvol[subvol] = {}
				elif isinstance(subvol_info[subvol],str):
					norm_subvol[subvol] = {'mountpoint':subvol_info[subvol]}
				else:
					norm_subvol[subvol] = subvol_info[subvol]
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
					result.dict[disk]['partitions'] = normalized_partitions
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
		for subvolume in value.get('btrfs',{}).get('subvolumes',{}):  # expect normalized contents
			if 'mountpoint' in value['btrfs']['subvolumes'][subvolume]:
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
		# if 'btrfs' in self.ds: # TODO this might be not needed anymore
			# self.ds['subvolumes'] = self.ds.get('btrfs',{}).get('subvolumes',{})
			# del self.ds['btrfs']
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
			# elif item == 'subvolumes' and self.ds.get(item): # TODO this might not be needed anymore
				# self.data['btrfs']['subvolumes'] = self.ds[item]
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
		if response == 'yes':
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
		# TODO It's a bit more complex than that
		if value[0]:
			self.ds['mountpoint'] = '/boot'
			self.ds['fs'] = 'FAT32'
			self.ds['encrypted'] = False
		return value[0]

	def _select_filesystem(self,prev):
		fstype_title = _('Enter a desired filesystem type for the partition: ')
		fstype = archinstall.Menu(fstype_title, archinstall.fs_types(), skip=False, preset_values=prev).run()
		if fstype != self.data.get('filesystem',{}).get('format'): # changed FS means reformat
			self.ds['wipe'] = True
		if fstype == 'btrfs':
			self.option('subvolumes').set_enabled(True)
		else:
			self.option('subvolumes').set_enabled(False)
		return fstype

	def _select_physical(self,prev):
		# TODO check if IDs have to change when you modify a partition, and if it is allowed
		from os import system
		# MINIMAL_SECTOR = 34
		MINIMAL_PARTITION_SIZE = 2 ** 11 # one MiB in sectors
		# MINIMAL_START_POS = 1024
		if self.data.get('uuid'): # an existing partition can not be physically changed
			return prev
		if not prev:
			prev = {}
		# we get the free list and if there exists prev we add this to the list
		if self.caller:
			total_size,sector_size,free = self.caller.gap_map(self.block_device)
		else:
			total_size,sector_size,free = list_free_space(self.block_device,'s')
		if prev:
			# we will include the selected chunck as free space, so we can expand it if necessary
			prev_line = [int(prev.get('start')),int(prev.get('size') + prev.get('start') - 1),prev.get('size'),'Current Location']
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
		# TODO define a minimum size for partitions
		for linea in free:
			if linea[2] < MINIMAL_PARTITION_SIZE:
				linea.append(_("Not suitable"))
		if prev:
			current_gap = [line[3] if len(line) == 4 else None for line in free].index('Current Location')
		else:
			current_gap = 0
		# TODO define a minimal start position
		# TODO standarize units for return code
		system('clear')
		print()
		print(f"List of free space at {self.block_device.path} in sectors")
		print()
		print("{:12} | {:12} | {:12}".format('start','end','size'))
		print("{}|{}|{}".format('-' * 13,'-' * 14,'-' * 14))
		for linea in free:
			if len(linea) == 3:
				print(f"{linea[0]:>12} | {linea[1]:>12} | {convert_units(linea[2],'GiB','s'):>12}GiB")
			else:
				print(f"{linea[0]:>12} | {linea[1]:>12} | {convert_units(linea[2],'GiB','s'):>12}GiB    {linea[3]}")
		print()
		# TODO check minimal size
		# TODO text with possible unit definition
		# TODO preselect optimal ¿? hole
		if prev:
			print(_("Current physical location selection"))
			print(f"{int(prev.get('start')):>12} | {int(prev.get('size') + prev.get('start') -1):>12} | {convert_units(prev.get('size'),'GiB','s'):>12}GiB")
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
			return {}
		# TODO partition reference if possible
		if prev is None:
			prev = {}
		return SubvolumeList(_("Manage btrfs subvolumes for current partition"),prev).run()

class DevList(archinstall.ListManager):
	def __init__(self,prompt,list):
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
		super().__init__(prompt,list,self.ObjectActions,self.ObjectNullAction,self.ObjectDefaultAction)
		bar = '|'
		if archinstall.arguments.get('long_form'):
			self.header = ((f"  {'identifier':^16}"
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
			self.header = ((f"  {'identifier':^16}"
						f"{bar}{'wipe':^5}"
						f"{bar}{'boot':^5}"
						f"{bar}{'encrypted':^7.7}"
						f"{bar}{'s. (GiB)':^8.8} "
						f"{bar}{'fs':^8}"
						f"{bar}{'mount at':^19}"
						f"{bar}{'used':^6}"),
						f"{'-' * 18}{bar}{'-'*5}{bar}{'-'*5}{bar}{'-'*7}{bar}{'-'*9}{bar}{'-'*8}{bar}{'-'*19}{bar}{'-'*6}")

	def reformat(self):
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
					if isinstance(subvolumes[subvol],str):
						mountlist.append(subvolumes[subvol])
					elif subvolumes[subvol].get('mountpoint'):
						mountlist.append(subvolumes[subvol]['mountpoint'])
				if mountlist:
					mount = f"{', '.join(mountlist):15.15}..."
				else:
					mount = blank
			else:
				mount = blank
			if entry.get('actual_subvolumes'):
				subvolumes = entry['actual_subvolumes']
				mountlist = []
				for subvol in subvolumes:
					if isinstance(subvolumes[subvol],str):
						mountlist.append(subvolumes[subvol])
					elif subvolumes[subvol].get('mountpoint'):
						mountlist.append(subvolumes[subvol]['mountpoint'])
				if mountlist:
					amount = f"//HOST({', '.join(mountlist):15.15})..."
				else:
					amount = blank
			elif entry.get('actual_mountpoint'):
				amount = f"//HOST{entry['actual_mountpoint']}"
			else:
				amount = blank
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
		self.reorder_data()
		tmp_list = list(filter(lambda x:not self.data[x].get('hide',False),self.data))
		return list(map(lambda x:pretty_disk(x,self.data[x]) if self.data[x]['class'] == 'disk' else pretty_part(x,self.data[x]),tmp_list))
		# ... beautfy the output of the list

	def action_list(self):
		disk_actions = (0,1,2,5)
		part_actions = (3,4,6,7)
		if self.target:
			key,value = list(self.target.items())[0]
		else:
			key = None
		if self.target[key].get('class') == 'disk':
			return [self.base_actions[i] for i in disk_actions]
		elif self.target[key].get('class') == 'gap':
			return [self.base_actions[1]]
		elif self.target[key].get('class') == 'partition':
			return [self.base_actions[i] for i in part_actions]
		else:
			return self.base_actions
		# ... if you need some changes to the action list based on self.target

	def exec_action(self):
		def ripple_delete(identifier,head=False):
			keys = list(self.data.keys())
			for entry in keys:
				if entry == identifier and not head:
					continue
				if entry.startswith(identifier):
					del self.data[entry]
			keys = list(self.partitions_to_delete.keys())
			for entry in keys:
				if entry.startswith(identifier):
					del self.partitions_to_delete[entry]

		if self.target:
			key,value = list(self.target.items())[0]
			if value.get('class') == 'disk':
				disk = key
			else:
				disk = value.get('parent')
		else:
			key = None
			value = None
			disk = None
		# reset
		if self.action == self.ObjectDefaultAction:
			self.data = self.base_data
			self.partitions_to_delete = {}
		# Add disk to installation set',          # 0
		elif self.action == self.ObjectActions[0]:
			# select harddrive still not on set
			# load its info and partitions into the list
			pass
		# Add partition',                         # 1
		elif self.action == self.ObjectActions[1]:
			# check if empty disk. A bit complex now. TODO sumplify
			if len([key for key in self.data if key.startswith(disk) and self.data[key]['class'] == 'partition']) == 0:
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
					if option not in add_menu.bottom_list:
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
				self.data.update({key:part_data})
				if is_empty_disk:
					self.data[disk]['wipe'] = True
				# TODO size comes in strange format
		# Clear disk (delete disk contents)',     # 2
		elif self.action == self.ObjectActions[2]:
			self.data[key]['wipe'] = True
			# no need to delete partitions in this disk
			ripple_delete(key,head=False)
			# Clear Partition & edit attributes',     # 3
		elif self.action == self.ObjectActions[3]:
			PartitionMenu(value,disk,self).run()
			if value:
				value['wipe'] = True
				self.data.update({key:value})
			# Edit partition attributes',             # 4
		elif self.action == self.ObjectActions[4]:
			PartitionMenu(value,disk,self).run()
			self.data.update({key:value})
			# Exclude disk from installation set',    # 5
		elif self.action == self.ObjectActions[5]:
			ripple_delete(key,head=True)
			# Exclude partition from installation set', # 6
		elif self.action == self.ObjectActions[6]:
			# TODO should restore to original values
			# del self.data[key]
			self.data[key]['hide'] = True
			self.data[key]['wipe'] = False
			# Delete partition'                       # 7
		elif self.action == self.ObjectActions[7]:
			if value.get('uuid'):
				self.partitions_to_delete.update(self.target)
			del self.data[key]

	def gap_map(self,block_device):
		gap_list = []
		if isinstance(block_device,archinstall.BlockDevice):
			disk = block_device.path
		else:
			disk = block_device
		tmp_gaps = [value for part,value in sorted(self.data.items()) if value.get('parent') == disk and value['class'] == 'gap']
		for gap in tmp_gaps:
			# and the off by one ¿?
			gap_list.append([gap['start'],gap['size'] + gap['start'] - 1 ,gap['size']])
		# the return values are meant to be compatible with list_free_space.
		return GLOBAL_BLOCK_MAP[disk]['size'],GLOBAL_BLOCK_MAP[disk]['sector_size'],gap_list

	def reorder_data(self):
		new_struct = {}
		tmp_disks = [disk for disk in sorted(list(self.data.keys())) if self.data[disk].get('class') == 'disk']
		for disk in tmp_disks:
			new_struct.update({disk:self.data[disk]})
			tmp_parts = [value for part,value in sorted(self.data.items()) if value.get('parent') == disk and value['class'] == 'partition']
			new_parts = create_gaps(tmp_parts,disk,GLOBAL_BLOCK_MAP[disk]['size'])
			new_struct[disk]['partitions'] = new_parts
		self.data = from_general_dict_to_display(new_struct)


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
			if result == options[0]:
				# TODO should we check if the directory exists as a mountpoint ?
				arguments['harddrives'] = []
				if 'disk_layout' in arguments:
					del arguments['disk_layout']
				return
			elif result in (options[1],options[2]):
				old_harddrives = arguments.get('harddrives', [])
				harddrives = archinstall.select_harddrives(old_harddrives)
				if not harddrives:
					return # TODO ought to be return to the menu
				arguments['harddrives'] = harddrives
				# in case the harddrives got changed we have to reset the disk layout as well
				# TODO is that needed now ?
				if old_harddrives != harddrives:
					arguments['disk_layouts'] = {}
				if result == options[1]:
					# we will create an standard layout, but will left open, editing it
					layout = get_default_partition_layout(harddrives) # TODO advanced options
				# elif result == options[2]:
					# layout = navigate_structure(arguments['harddrives'])
			elif result == options[3]:
				harddrives = []
				# layout = navigate_structure()
			else:
				pass
			return from_general_dict_to_display(integrate_layout_in_global_map(harddrives,layout))
		else:
			return


list_layout = frontpage()
if not list_layout:
	exit()
# pprint(list_layout)
result = DevList('*** Disk Layout ***',list_layout).run()
# pprint(result)
archinstall.arguments['disk_layouts'] = convert_to_disk_layout(result)
archinstall.arguments['harddrives'] = harddrives = [archinstall.BlockDevice(key) for key in archinstall.arguments['disk_layouts']]
config_output = archinstall.ConfigurationOutput(archinstall.arguments)
config_output._disk_layout_file = 'layout_diskmanager.json'
if not archinstall.arguments.get('silent'):
	config_output.show()
config_output.save()
