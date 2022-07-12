from archinstall.lib.menu.list_manager import ListManager
from archinstall.lib.output import log
from .dataclasses import DiskSlot, GapSlot, PartitionSlot, parent_from_list, actual_mount
from .output import FormattedOutput
from .partition_menu import PartitionMenu
# from diskmanager.generator import generate_layout
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
		new_mapa += disk.device_map(mapa)
	return new_mapa

class DevList(ListManager):

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
			self.partitions_to_delete = []
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
			return self._action_add_partition(object,data)
		# Clear disk (delete disk contents)',     # 2
		elif action == self.ObjectActions[2]:
			return self._action_clear_disk(object,data)
		# Clear Partition & edit attributes',     # 3
		elif action == self.ObjectActions[3]:
			return self._action_clear_partition(object,data)
		# Edit partition attributes',             # 4
		elif action == self.ObjectActions[4]:
			return self._action_edit_partition(object,data)
		# Exclude disk from installation set',    # 5
		elif action == self.ObjectActions[5]:
			return self._action_exclude_disk(object,data)
		# Exclude partition from installation set', # 6
		elif action == self.ObjectActions[6]:
			# BUG for the time being disallowed. Current implementation is faulty
			return self._action_not_implemented(object,data)
		# Delete partition'                       # 7
		elif action == self.ObjectActions[7]:
			return self._action_delete_partition(object,data)
		return data

	def _action_not_implemented(self,object,data):
		log('Action still not implemented')
		return data

	def _action_reset(self,object,data):
		self.partitions_to_delete = {}
		return self._original_data

	def _action_add_partition(self,object,data):
		disk = parent_from_list(object, data)
		if len(disk.partition_list(data)) == 0:
			is_empty_disk = True
		else:
			is_empty_disk = False
		if isinstance(object,GapSlot):
			part_data = PartitionSlot(object.device,object.startInput,object.sizeInput,wipe=True)
		else:
			part_data = PartitionSlot(object.device, -1, -1, wipe=True)  # Something has to be done with this

		add_menu = PartitionMenu(part_data,self)
		# for some reason this code blocks temporarliy set out of process
		# with PartitionMenu(part_data,self) as add_menu:
		# 	exit_menu = False
		# 	for option in add_menu.list_options():
		# 		# TODO this is not what i need
		# 		if option in ('location','mountpoint','filesystem','subvolumes','boot','encrypted'):
		# 			add_menu.synch(option)
		# 			add_menu.exec_option(option)
		# 			# TODO broken execution there
		# 			if option == 'location' and add_menu.option('location').get_selection() is None:
		# 				exit_menu = True
		# 				break
		# 	if not exit_menu:
		# 		add_menu.run()
		# 	else:
		# 		add_menu.exec_option(add_menu.cancel_action)
		add_menu.run()
		if add_menu.option(add_menu.cancel_action).get_selection():
			return data
		if part_data:
			data.append(part_data)
			if is_empty_disk:
				disk.wipe = True
		return data

	def _action_clear_disk(self,object,data):
		object.wipe = True
		# no need to delete partitions in this disk
		self._ripple_delete(object,data,head=False)
		return data

	def _action_clear_partition(self,object,data):
		PartitionMenu(object,self).run()  # TODO don't like the return control
		if object:
			object.wipe = True
		return data

	def _action_delete_partition(self,object,data):
		if actual_mount(object):
			log('Can not delete partition {object.path}, because it is in use')  # TODO it doesn't show actually
			return data
		elif object.uuid:
			self.partitions_to_delete.append(object)
		key = data.index(object)
		del data[key]
		return data

	def _action_edit_partition(self,object,data):
		PartitionMenu(object,self).run()
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
