# WORK IN PROGRESS
from copy import deepcopy
import archinstall

from archinstall.diskmanager.helper import convert_units

from typing import Any, TYPE_CHECKING, Dict, Optional, List

from archinstall.examples.diskmanager import list_free_space, align_entry, merge_list, location_to_gap, \
	from_global_to_partial_pct, eval_percent, unit_best_fit

if TYPE_CHECKING:
	_: Any


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
		return archinstall.SubvolumeList(_("Manage btrfs subvolumes for current partition"),prev).run()
