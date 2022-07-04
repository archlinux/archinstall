import archinstall
from archinstall.diskmanager.dataclasses import *
from archinstall.diskmanager.discovery import *
from archinstall.diskmanager.helper import *
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

pprint(hw_discover())
# create_global_block_map()

#mapa = []
#mapa.append(PartitionSlot('/dev/loop0',4096,512000,'/boot','ext4')) # TODO path
#mapa.append(PartitionSlot('/dev/loop0',1000000,6000000,'ext4','/')) # TODO path
#mapa.append(DiskSlot('/dev/loop0',0,'8GiB')) # TODO size in not integer notation

#mapa = sorted(mapa)
#print(PartitionSlot('paco',1,1).parent(mapa))
#for entry in create_gap_list(mapa):
	#print('\t',entry.sizeN,entry.sizeInput,entry.size,entry.start,entry.end,type(entry))
