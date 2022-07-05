import archinstall
from archinstall.diskmanager.dataclasses import *
from archinstall.diskmanager.discovery import *
from archinstall.diskmanager.helper import *
from archinstall.diskmanager.output import *
from typing import List, Any, Dict
from pprint import pprint
from dataclasses import asdict


def create_gap_list(mapa):
	""" takes a list of slots and creates an equivalent list with (updated) gaps """
	new_mapa = []
	for disk in sorted([entry for entry in mapa if isinstance(entry,DiskSlot)]):
		new_mapa.append(disk)
		new_mapa += disk.create_gaps(mapa)
	return new_mapa

def format_to_list_manager(data, field_list=None):
	filter = ['path','device','start','sizeN','type','wipe','encripted','boot','actual_mountpoint','filesystem','actual_subvolumes']
	table = FormattedOutput.as_table_filter(data,None,filter)
	rows = table.split('\n')
	# these are the header rows of the table and do not map to any User obviously
	# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
	# the selectable rows so the header has to be aligned
	display_data = {f'  {rows[0]}': None, f'  {rows[1]}': None}

	for row, payload in zip(rows[2:], data):
		row = row.replace('|', '\\|')
		display_data[row] = payload

	return display_data


class HwMap(archinstall.ListManager):
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
		pprint(FormattedOutput.value(objeto))
		input()
		return data
	def filter_options(self, selection :Any, options :List[str]) -> List[str]:
		return options

hw_map_data = hw_discover()
HwMap('List of storage at this machine',hw_map_data,[],['Show']).run()
# create_global_block_map()

#mapa = []
#mapa.append(PartitionSlot('/dev/loop0',4096,512000,'/boot','ext4')) # TODO path
#mapa.append(PartitionSlot('/dev/loop0',1000000,6000000,'ext4','/')) # TODO path
#mapa.append(DiskSlot('/dev/loop0',0,'8GiB')) # TODO size in not integer notation

#mapa = sorted(mapa)
#print(PartitionSlot('paco',1,1).parent(mapa))
#for entry in create_gap_list(mapa):
	#print('\t',entry.sizeN,entry.sizeInput,entry.size,entry.start,entry.end,type(entry))

