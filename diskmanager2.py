import archinstall
from archinstall.diskmanager.dataclasses import DiskSlot, GapSlot, PartitionSlot
from archinstall.diskmanager.discovery import layout_to_map, hw_discover
from archinstall.diskmanager.generator import generate_layout
from typing import List, Any, Dict, Optional
from pprint import pprint


# TODO this ougth come with the dataclass
from archinstall.diskmanager.partition_list import format_to_list_manager, create_gap_list, DevList


class HwMap(archinstall.ListManager):

	def __init__(
		self,
		prompt: str,
		entries: List[Any],
		base_actions: List[str],
		sub_menu_actions: List[str]
	):
		entries = create_gap_list(entries)  # list will be substituted with one with gaps
		super().__init__(prompt,entries,base_actions,sub_menu_actions)

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
		objeto = self._get_selected_object(entry)
		pprint(objeto.as_dict())
		# this is common for all action.
		my_data = create_gap_list(data)
		return my_data

	def filter_options(self, selection :Any, options :List[str]) -> List[str]:
		return options

# TODO rename btrfs attribute to subvolumes
# TODO verify what archinstall.__init__ does to the start attribute. seems it is normalized before handling
from pudb import set_trace
set_trace()
hw_map_data = hw_discover()
# hw_map_data = layout_to_map(archinstall.arguments.get('disk_layouts',{}))
DevList('List of storage entities',hw_map_data).run()
#harddrives,disk_layout = generate_layout(hw_map_data)
#HwMap('List of storage at this machine',hw_map_data,[],['Show']).run()
# create_global_block_map()

# mapa = []
# mapa.append(PartitionSlot('/dev/loop0',4096,512000,'/boot','ext4')) # TODO path
# mapa.append(PartitionSlot('/dev/loop0',1000000,6000000,'ext4','/')) # TODO path
# mapa.append(DiskSlot('/dev/loop0',0,'8GiB')) # TODO size in not integer notation
#
# mapa = sorted(mapa)
# print(PartitionSlot('paco',1,1).parent(mapa))
# for entry in create_gap_list(mapa):
# 	print('\t',entry.sizeN,entry.sizeInput,entry.size,entry.start,entry.end,type(entry))
