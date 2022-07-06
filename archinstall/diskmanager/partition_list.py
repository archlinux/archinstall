import archinstall
from archinstall.diskmanager.dataclasses import DiskSlot, GapSlot, PartitionSlot, parent_from_list, actual_mount
from archinstall.diskmanager.discovery import layout_to_map, hw_discover
from archinstall.diskmanager.output import FormattedOutput
from archinstall.diskmanager.generator import generate_layout
from typing import List, Any, Dict, Optional, TYPE_CHECKING
if TYPE_CHECKING:
	_: Any

def format_to_list_manager(data, field_list=None):
	# TODO  short and long form
	filter = ['path','start','sizeN','type','wipe','encrypted','boot','filesystem','mountpoint', 'actual_mountpoint','uuid']
	table = FormattedOutput.as_table_filter(data,filter,'as_dict_str')
	rows = table.split('\n')
	# these are the header rows of the table and do not map to any User obviously
	# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
	# the selectable rows so the header has to be aligned
	display_data = {f'  {rows[0]}': None, f'  {rows[1]}': None}

	for row, payload in zip(rows[2:], data):
		row = row.replace('|', '\\|')
		display_data[row] = payload

	return display_data

def create_gap_list(mapa):
	""" takes a list of slots and creates an equivalent list with (updated) gaps """
	new_mapa = []
	for disk in sorted([entry for entry in mapa if isinstance(entry,DiskSlot)]):
		new_mapa.append(disk)
		new_mapa += disk.create_gaps(mapa)
	return new_mapa

class DevList(archinstall.ListManager):

	def __init__(
		self,
		prompt: str,
		entries: List[Any]
	):
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
		entries = create_gap_list(entries)  # list will be substituted with one with gaps
		self.ObjectDefaultAction = 'Reset'
		self.partitions_to_delete = []
		super().__init__(prompt,entries,[self.ObjectDefaultAction],self.ObjectActions)

	def run(self):
		result_list = super().run()
		# TODO there is no self.action by now
		if self.last_choice.value != self._confirm_action:
			self.partitions_to_delete = {}
		return result_list, self.partitions_to_delete

	def _get_selected_object(self,selection):
		pos = self._data.index(selection)
		return self._data[pos]

	def selected_action_display(self, selection: Any) -> str:
		objeto = self._get_selected_object(selection)
		# TODO as dataclass method
		if isinstance(objeto,DiskSlot):
			return f'disk {objeto.device}'
		elif isinstance(objeto,GapSlot):
			return f'gap {objeto.device}@{objeto.start}'
		elif isinstance(objeto,PartitionSlot):
			if objeto.path:
				return f'partition {objeto.path}'
			else:
				return f'partition {objeto.device}@{objeto.start}'
		return selection

	def reformat(self, data: List[Any]) -> Dict[str, Any]:
		# raw_result = self._header() | {f'{item}':item for item in sorted(data)}
		# return raw_result
		return format_to_list_manager(data)

	def handle_action(self, action: Any, entry: Optional[Any], data: List[Any]) -> List[Any]:
		# this is common for all action.
		my_data = create_gap_list(self._exec_action(action,entry,data))
		return my_data

	def filter_options(self, selection :Any, options :List[str]) -> List[str]:
		# filter which actions to show for an specific selection
		target = self._get_selected_object(selection)
		disk_actions = (0,1,2,5)
		part_actions = (3,4,7)  # BUG hide partition disallowed for the time being (3,4,6,7)
		match target:
			case DiskSlot():
				return [options[i] for i in disk_actions]
			case GapSlot():
				return [options[1]]
			case PartitionSlot():
				return [options[i] for i in part_actions]
			case _:
				return options

	def _exec_action(self,action,object,data):
		disk = None # parent_from_list(object,data)
		# reset
		if action == self.ObjectDefaultAction:
			return self._action_reset(object,data)
		# Add disk to installation set',          # 0
		elif action == self.ObjectActions[0]:
			# select harddrive still not on set
			# load its info and partitions into the list
			return self._action_not_implemented(object,data)
		# Add partition',                         # 1
		elif action == self.ObjectActions[1]:
			return self._action_not_implemented(object, data)
			return self._action_add_partition(key,value,disk,data)
		# Clear disk (delete disk contents)',     # 2
		elif action == self.ObjectActions[2]:
			return self._action_clear_disk(object,data)
		# Clear Partition & edit attributes',     # 3
		elif action == self.ObjectActions[3]:
			return self._action_not_implemented(object, data)
			return self._action_clear_partition(key,value,disk,data)
		# Edit partition attributes',             # 4
		elif action == self.ObjectActions[4]:
			return self._action_not_implemented(object, data)
			return self._action_edit_partition(key,value,disk,data)
		# Exclude disk from installation set',    # 5
		elif action == self.ObjectActions[5]:
			return self._action_exclude_disk(object,data)
		# Exclude partition from installation set', # 6
		elif action == self.ObjectActions[6]:
			# BUG for the time being disallowed. Current implementation is faulty
			return self._action_not_implemeted(key,value,disk,data)
		# Delete partition'                       # 7
		elif action == self.ObjectActions[7]:
			return self._action_delete_partition(object,data)
		return data

	def _action_not_implemented(self,object,data):
		archinstall.log('Action still not implemented')
		return data

	def _action_reset(self,object,data):
		self.partitions_to_delete = {}
		return self._original_data

	def _action_clear_disk(self,object,data):
		object.wipe = True
		# no need to delete partitions in this disk
		self._ripple_delete(object,data,head=False)
		return data

	def _action_delete_partition(self,object,data):
		if actual_mount(object):
			archinstall.log('Can not delete partition {object.path}, because it is in use')  # TODO it doesn't show actually
			return data
		elif object.uuid:
			self.partitions_to_delete.append(object)
		key = data.index[object]
		del data[key]
		return data

	def _action_exclude_disk(self,object,data):
		self._ripple_delete(object,data, head=True)
		return data

	def _ripple_delete(self, object, data, head):
		if not isinstance(object,DiskSlot):
			return data
		children = object.children(data)
		for child in children:
			idx = data.index(child)
			if isinstance(child,PartitionSlot) and child.uuid:
				try:
					idx_del = self.partitions_to_delete.index(child)
					del self.partitions_to_delete[idx_del]
				except ValueError:
					pass
			del data[idx]
		if head:
			idx = data.index(object)
			del data[idx]
		return data
		# placeholder

# TODO
#    * _ripple_delete
#    * gap_map
#    reorder_data
#    action list -> filter_option
class DevList_old(archinstall.ListManager):
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
		self._ripple_delete(key, head=False)
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
		self._ripple_delete(key, head=True)
		return data

	def _action_delete_partition(self,key,value,disk,data):
		if self.amount(value):
			print('Can not delete partition, because it is in use')  # TODO it doesn't show actually
			return
		elif value.get('uuid'):
			self.partitions_to_delete.update({key:value})
		del data[key]
		return data

	def _ripple_delete(self, key, head):
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


