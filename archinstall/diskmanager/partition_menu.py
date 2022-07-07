# WORK IN PROGRESS
from copy import deepcopy
from dataclasses import asdict, dataclass

import archinstall
from archinstall.diskmanager.dataclasses import PartitionSlot, DiskSlot
from archinstall.diskmanager.discovery import hw_discover

from archinstall.diskmanager.helper import convert_units, unit_best_fit, split_number_unit

from typing import Any, TYPE_CHECKING, Union   # , Dict, Optional, List

# from archinstall.examples.diskmanager import list_free_space, align_entry, merge_list, location_to_gap, from_global_to_partial_pct, eval_percent, unit_best_fit
from archinstall.diskmanager.output import FormattedOutput

if TYPE_CHECKING:
	_: Any

# TODO generalize
@dataclass
class FlexSize:
	# TODO check nones
	input_value: Union[str,int]

	@property
	def sectors(self):
		return int(convert_units(self.input_value,'s','s'))

	@property
	def normalized(self):
		return unit_best_fit(self.sectors,'s')

	def pretty_print(self):
		return f"{self.sectors:,} ({self.normalized})"

	def adjust_other(self,other):
		unit = None
		if other.input_value.strip().endswith('%'):
			pass
		else:
			_, unit = split_number_unit(self.input_value)
			if unit:
				other.input_value = f"{convert_units(other.sectors, unit, 's')} {unit.upper()}"

# TODO check real format of (mount|format)_options
# A prompt i need
class PartitionMenu(archinstall.GeneralMenu):
	def __init__(self,object,caller=None,disk=None):
		# Note if object.sizeInput has -1 it is a new partition. is a small trick to keep object passed as reference
		self.data = object
		self.caller = caller
		# if there is a listmanager disk comes from the list not the parameter.
		# if no parameter
		self._list = self.caller._data if isinstance(caller,archinstall.ListManager) else []
		if self._list:
			self.disk = object.parent_in_list(self._list)
		elif disk:
			self.disk = disk
		else:
			my_disk = archinstall.BlockDevice(object.device)
			self.disk = DiskSlot(my_disk.device,0,my_disk.size,my_disk.partition_type)
		self.ds = {}
		self.ds = self._conversion_from_object()
		super().__init__(data_store=self.ds)

	def _conversion_from_object(self):
		my_dict = deepcopy(asdict(self.data) if isinstance(self.data,PartitionSlot) else {}) # TODO verify independence
		print('before')
		print(my_dict)
		if my_dict['startInput'] != -1:
			my_start = FlexSize(my_dict['startInput'])
		else:
			my_start = None
		if my_dict['sizeInput'] != -1:
			my_size = FlexSize(my_dict['sizeInput'])
		else:
			my_size = None
		my_dict['location'] = {'start':my_start, 'size':my_size}
		del my_dict['startInput']
		del my_dict['sizeInput']
		if 'btrfs' in my_dict:
			my_dict['subvolumes'] = deepcopy(my_dict['btrfs'])
			del my_dict['btrfs']
		# temporary
		if 'type' not in my_dict:
			my_dict['type'] = 'primary'
		return my_dict

	def _conversion_to_object(self):
		for item in self.ds:
			if item == 'location':
				self.data['startInput'] = self.ds['location'].get('start',FlexSize(None)).input_value
				self.data['sizeInput'] = self.ds['location'].get('size', FlexSize(None)).input_value
			elif item == 'subvolumes':
				self.data['btrfs'] = self.ds['subvolumes']
			else:
				self.data[item] = self.ds[item]

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

							dependencies=['filesystem'],enabled=True)
		self._menu_options['filesystem'] = archinstall.Selector(str(_("File System Type")),
							self._select_filesystem,
							enabled=True)
		self._menu_options['filesystem_format_options'] = archinstall.Selector(str(_("File System Format Options")),
							lambda prev: self._generic_string_editor(str(_('Edit format options :')),prev),
							dependencies=['filesystem'],enabled=True)
		self._menu_options['filesystem_mount_options'] = archinstall.Selector(str(_("File System Mount Options")),
							lambda prev: self._generic_string_editor(str(_('Edit mount options :')),prev),
							dependencies=['filesystem'],enabled=True)
		self._menu_options['subvolumes'] = archinstall.Selector(str(_("Btrfs Subvolumes")),
							self._manage_subvolumes,
							dependencies=['filesystem'],
							enabled=True if self.ds.get('filesystem') == 'btrfs' else False) # TODO only if it is btrfs
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
			if self.ds.get('filesystem') == 'btrfs':
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
		self._conversion_to_object()

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
		if location.get('start'):
			my_start = location['start'].pretty_print()
		else:
			my_start = '_'
		if location.get('size'):
			my_size = location['size'].pretty_print()
		else:
			my_size = '_'
		return(f' start : {my_start}, size : {my_size}')

	def _select_boot(self,prev):
		value = self._generic_boolean_editor(str(_('Set bootable partition :')),prev),
		# only a boot per disk is allowed
		if value[0] and self._list:
			bootable = [entry for entry in self.disk.partition_list() if entry.boot]
			if len(bootable) > 0:
				archinstall.log(_('There exists another bootable partition on disk. Unset it before defining this one'))
				if self.disk.type.upper() == 'GPT':
					archinstall.log(_('On GPT drives ensure that the boot partition is an EFI partition'))
				input()
			return prev
		# TODO It's a bit more complex than that. This is only for GPT drives
		# problem is when we set it backwards
		if value[0] and self.disk.type.upper() == 'GPT':
			self.ds['mountpoint'] = '/boot'
			self.ds['filesystem'] = 'FAT32'
			self.ds['encrypted'] = False
			self.ds['type'] = 'EFI'
		return value[0]

	def _select_filesystem(self,prev):
		fstype_title = _('Enter a desired filesystem type for the partition: ')
		fstype = archinstall.Menu(fstype_title, archinstall.fs_types(), skip=False, preset_values=prev).run()
		# escape control
		if fstype.type_ == archinstall.MenuSelectionType.Esc:
			return prev
		# changed FS means reformat if the disk exists
		if fstype.value != prev and self.ds.get('uuid'):
			self.ds['wipe'] = True
		if fstype.value == 'btrfs':
			self.option('subvolumes').set_enabled(True)
		else:
			self.option('subvolumes').set_enabled(False)
		return fstype.value

	# this block is for assesing a space allocation. probably it ougth to be taken off the class
	def _get_gaps_in_disk(self,list_to_check):
		if list_to_check is None:
			tmp_list = hw_discover([self.disk.device])
			return self._get_gaps_in_disk(tmp_list)
		elif len(list_to_check) == 0:
			return []
		else:
			tmp_list = [part for part in self.disk.partition_list(list_to_check) if part != self.data]
			return self.disk.gap_list(tmp_list)

	def _show_gaps(self,gap_list,prev):
		screen_data = FormattedOutput.as_table_filter(gap_list,['start','end','size','sizeN'])
		print('Current free space is')
		print(screen_data)
		print('Current allocation is',prev)

	def _select_physical(self,prev):
		# from os import system
		# an existing partition can not be physically changed
		if self.ds.get('uuid'):
			return prev
		if not prev:
			prev = {}
		gap_list = self._get_gaps_in_disk(self._list)
		self._show_gaps(gap_list,prev)
		input()
		return prev
		# # we get the free list and if there exists prev we add this to the list
		# if self.caller:
		# 	total_size,sector_size,free = self.caller.gap_map(self.block_device)
		# else: # Might not be needed, but permits to execute standalone
		# 	total_size,sector_size,free = list_free_space(self.block_device,'s')
		# 	total_size = int(total_size[:-1])
		#
		# ALIGNMENT = convert_units(archinstall.arguments.get('align',0),'s','s') # 2**13
		# MIN_PARTITION = ALIGNMENT if ALIGNMENT > 1 else 2**13 # 4 MiB
		# LAST_SECTOR = total_size - 33 # last assignable sector (we leave 34 sectors por internal info
		#
		# def align_gaps(free_slots,ALIGNMENT,MIN_PARTITIONS,LAST_SECTOR):
		# 	#
		# 	# the gap list has to be renormalized thru the use of ALIGNMENT,
		# 	# so we only asign aligned partitions to the structure we define
		# 	#
		# 	norm_free_slot = []
		# 	for slot in free_slots:
		# 		norm_slot = align_entry(slot,ALIGNMENT,LAST_SECTOR)
		# 		if norm_slot[2] > 0:
		# 			norm_free_slot.append(norm_slot)
		# 		else:
		# 			continue
		# 		# mark unavailable slots
		# 		if len(norm_free_slot[-1]) == 3:
		# 			norm_free_slot[-1].append('')
		# 		if norm_free_slot[-1][2] < MIN_PARTITION:
		# 			norm_free_slot[-1][3] += ' too short'
		# 	return norm_free_slot
		#
		# def show_free_slots(free,prev,ALIGNMENT):
		# 	# print("<{:>20,}{:>20,}{:>20,} {}".format(*norm_free_slot[-1]))
		# 	print()
		# 	print(f"List of free space at {self.block_device.path} in sectors")
		# 	print()
		# 	print("{:20} | {:20} | {:20}".format('start','end','size'))
		# 	print("{}|{}|{}".format('-' * 21,'-' * 21,'-' * 21))
		# 	for linea in free:
		# 		if len(linea) == 3:
		# 			print(f"{linea[0]:>20,} | {linea[1]:>20,} | {unit_best_fit(linea[2]):>12}")
		# 		else:
		# 			print(f"{linea[0]:>20,} | {linea[1]:>20,} | {unit_best_fit(linea[2]):>12}    {linea[3]}")
		# 	print()
		# 	# TODO check minimal size
		# 	# TODO text with possible unit definition
		# 	# TODO preselect optimal ¿? hole
		# 	if prev:
		# 		print(_("Current physical location selection"))
		# 		print(f"{int(prev.get('start')):>20,} | {int(prev.get('size') + prev.get('start') -1):>20,} | {unit_best_fit(prev.get('size')):>12}")
		# 		if ALIGNMENT > 1:
		# 			print(_("Current physical location selection; aligned"))
		# 			norm_slot = align_entry([int(prev.get('start')),int(prev.get('size')) + int(prev.get('start')) - 1,int(prev.get('size'))],ALIGNMENT,LAST_SECTOR)
		# 			print(f"{norm_slot[0]:>20,} | {norm_slot[1]:>20,} | {unit_best_fit(norm_slot[2]):>12}")
		# 	print()
		#
		# # we will include the selected chunck as free space, so we can expand it if necessary
		# if prev:
		# 	merge_list(free,location_to_gap(prev,'Current Location'))
		# # normalize free space according to alignment
		# free = align_gaps(free,ALIGNMENT,MIN_PARTITION,LAST_SECTOR)
		#
		# if prev:
		# 	current_gap = [line[3] if len(line) == 4 else None for line in free].index('Current Location')
		# else:
		# 	current_gap = 0
		# # TODO define a minimal start position
		# # TODO standarize units for return code
		# system('clear')
		# show_free_slots(free,prev,ALIGNMENT)
		#
		# starts = str(int(prev.get('start'))) if prev.get('start') else ''
		# if prev.get('sizeG'):
		# 	# TODO percentages back
		# 	if prev['sizeG'].strip()[-1] == '%':
		# 		size = from_global_to_partial_pct(prev['sizeG'],prev['start'],free[current_gap][1] - prev['start'] + 1,self.block_device.path)
		# 	else:
		# 		size = f"{prev.get('sizeG')}"
		# else:
		# 	size = f"{prev.get('size')}" if prev.get('size') else ''
		# while True:
		# 	if prev:
		# 		prompt = _("Define a start sector for the partition. Enter a value or \n"
		# 				"c to get the first sector of the current slot \n"
		# 				"q to quit \n"
		# 				"==> ")
		# 	else:
		# 		prompt = _("Define a start sector for the partition. Enter a value or \n"
		# 				"f to get the first sector of the first free slot which can hold a partition\n"
		# 				"l to get the first sector of the last free slot \n"
		# 				"q to quit \n"
		# 				"==> ")
		# 	starts = archinstall.TextInput(prompt,starts).run()
		# 	inplace = False
		# 	if starts.lower() == 'q':
		# 		if prev:
		# 			return prev
		# 		else:
		# 			return None
		# 	elif starts.lower() == 'f':
		# 		# TODO check really which is the first allocatable sector in a disk
		# 		starts = free[0][0]
		# 	elif starts.lower() == 'l':
		# 		starts = free[-1][0]
		# 	elif starts.lower() == 'c':
		# 		starts = free[current_gap][0]
		# 	else:
		# 		starts = int(convert_units(starts,'s','s')) # default value are sectors
		# 	maxsize = 0
		# 	endgap = 0
		# 	for gap in free:
		# 		# asume it is always sectors
		# 		if int(gap[0]) <= int(starts) <= int(gap[1]):
		# 			endgap = int(gap[1])
		# 			maxsize = int(gap[1]) - starts + 1 # i think i got it right
		# 			maxsize_g = convert_units(f"{maxsize}s",'GiB')
		# 			inplace = True
		# 			break
		# 	if not inplace:
		# 		print(_("Selected sector {} outside an empty gap").format(starts))
		# 	else:
		# 		break
		# while True:
		# 	size = archinstall.TextInput(_("Define a size for the partition \n(max {} sectors / {}GiB), a percentaje of the free space (ends with %),\n or q to quit \n ==> ").format(maxsize,maxsize_g),size).run()
		# 	if size.lower() == 'q':
		# 		if prev:
		# 			return prev
		# 		else:
		# 			return None
		# 	if size.endswith('%'):
		# 		size_s,size = eval_percent(size,starts,endgap,self.block_device.path)
		# 	else:
		# 		size_s = convert_units(size,'s','s')
		# 	# TODO when they match something fails ¿? decimals ?
		# 	if size_s > maxsize:
		# 		print(f"Size is too big for selected  gap. {size_s} > {maxsize} Reduce it to fit")
		# 	else: # TODO
		# 		break
		# if size.lower().strip()[-1] in ('b','%'):
		# 	return {'start':starts,'size':size_s,'sizeG':size}
		# else:
		# 	return {'start':starts,'size':size_s}

	def _manage_subvolumes(self,prev):
		if self.option('filesystem').get_selection() != 'btrfs':
			return []
		if prev is None:
			prev = []
		return archinstall.SubvolumeList(_("Manage btrfs subvolumes for current partition"),prev).run()
