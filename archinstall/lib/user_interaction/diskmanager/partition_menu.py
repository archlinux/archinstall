# WORK IN PROGRESS
from copy import deepcopy, copy
from dataclasses import asdict
from os import system

from archinstall.lib.disk import BlockDevice, fs_types
from ...output import log, FormattedOutput

from archinstall.lib.menu.menu import Menu
from archinstall.lib.menu.text_input import TextInput
from archinstall.lib.menu.selection_menu import GeneralMenu, Selector
from archinstall.lib.menu.list_manager import ListManager
from archinstall.lib.user_interaction.subvolume_config import SubvolumeList

from .dataclasses import PartitionSlot, DiskSlot, StorageSlot
from .discovery import hw_discover
from .helper import unit_best_fit, units_from_model

from typing import Any, TYPE_CHECKING, Callable, Union, Dict, List  # , Dict, Optional, List

if TYPE_CHECKING:
	_: Any


# TODO accept empty target if disk is set, to avoid the -1 stuff
class PartitionMenu(GeneralMenu):
	def __init__(self, target: StorageSlot, caller: Callable = None, disk: Union[DiskSlot,str] = None):
		"""
		Arguments
		target  the slot we will be editing
		caller  the routine which calls the menu. Used to extract some information if avaliable
		disk    the disk the partition is/will be. Usually not need as it can be recovered from caller		else:

		"""
		# Note if target.sizeInput has -1 it is a new partition. is a small trick to keep ,target passed as reference
		self.data = target
		self.caller = caller
		# if there is a listmanager disk comes from the list not the parameter.
		# if no parameter
		self._list = self.caller._data if isinstance(caller, ListManager) else []
		if self._list:
			self.disk = target.parent(self._list)
		elif disk:
			self.disk = disk
			my_disk = BlockDevice(target.device)
			self.disk = DiskSlot(my_disk.device, 0, my_disk.size, my_disk.partition_type)
		self.ds = {}
		self.ds = self._conversion_from_object()
		self._original_data = deepcopy(self.ds)
		super().__init__(data_store=self.ds)

	def _conversion_from_object(self) -> Dict[str,Any]:
		""" from the PartitionSlot dataclass to a dict editable by a GeneralMenu derivative (a dict) """
		# WARNING asdict converts embeded dataclasses also as dicts
		my_dict = asdict(self.data) if isinstance(self.data, PartitionSlot) else {}
		my_dict['location'] = StorageSlot(self.data.device, self.data.start, self.data.size)
		del my_dict['startInput']
		del my_dict['sizeInput']
		if 'btrfs' in my_dict:
			my_dict['subvolumes'] = deepcopy(self.data.btrfs)
			del my_dict['btrfs']
		if 'actual_subvolumes' in my_dict:
			my_dict['actual_subvolumes'] = deepcopy(self.data.actual_subvolumes)
		# temporary as long as we don't have a selection list for them
		if my_dict.get('filesystem_format_options',[]):
			my_dict['filesystem_format_options'] = ','.join(self.data.filesystem_format_options)
		if my_dict.get('filesystem_mount_options',[]):
			my_dict['filesystem_mount_options'] = ','.join(self.data.filesystem_mount_options)
		# temporary
		if 'type' not in my_dict:
			my_dict['type'] = 'primary'
		return my_dict

	def _conversion_to_object(self):
		""" from the GeneralMenu._data_store dictionary to a PartitionSlot
		TO access the elements dynamicly it uses __setitem__
		"""
		for item in self.ds:
			if item == 'location':
				self.data.startInput = self.ds['location'].startInput
				self.data.sizeInput = self.ds['location'].sizeInput
			elif item == 'subvolumes':
				self.data.btrfs = self.ds['subvolumes']
			elif item == 'filesystem_format_options' and self.ds['filesystem_format_options']:
				self.data.filesystem_format_options = self.ds['filesystem_format_options'].split(',')
			elif item == 'filesystem_mount_options' and self.ds['filesystem_mount_options']:
				self.data.filesystem_mount_options = self.ds['filesystem_mount_options'].split(',')
			else:
				self.data[item] = self.ds[item]

	def _setup_selection_menu_options(self):
		self._menu_options['location'] = Selector(str(_("Physical layout")),
									self._select_physical,
									display_func=self._show_location,
									enabled=True)
		self._menu_options['type'] = Selector(str(_("Partition type")),
							enabled=False)
		self._menu_options['mountpoint'] = Selector(str(_("Mount Point")),
							lambda prev: self._generic_string_editor(str(_('Edit Mount Point :')), prev),
							dependencies=['filesystem'], enabled=True)
		self._menu_options['filesystem'] = Selector(str(_("File System Type")),
							self._select_filesystem,
							enabled=True)
		self._menu_options['filesystem_format_options'] = Selector(str(_("File System Format Options")),
							lambda prev: self._generic_string_editor(str(_('Edit format options :')), prev),
							dependencies=['filesystem'], enabled=True)
		self._menu_options['filesystem_mount_options'] = Selector(str(_("File System Mount Options")),
							lambda prev: self._generic_string_editor(str(_('Edit mount options :')), prev),
							dependencies=['filesystem'], enabled=True)
		self._menu_options['subvolumes'] = Selector(str(_("Btrfs Subvolumes")),
							self._manage_subvolumes,
							dependencies=['filesystem'],
							enabled=True if self.ds.get('filesystem') == 'btrfs' else False)
		self._menu_options['boot'] = Selector(str(_("Is bootable")),
							self._select_boot,
							enabled=True)
		self._menu_options['encrypted'] = Selector(str(_("Encrypted")),
							lambda prev: self._select_encryption(str(_('Set ENCRYPTED partition :')), prev),
							enabled=True)
		self._menu_options['wipe'] = Selector(str(_("Delete content")),
							lambda prev:self._generic_boolean_editor(str(_('Do you want to wipe the contents of the partition')),prev),
							enabled=True)
		# readonly options
		if self.ds.get('uuid'):
			self._menu_options['actual_mountpoint'] = Selector(str(_("Actual mount")),
								enabled=True)
			if self.ds.get('filesystem') == 'btrfs':
				self._menu_options['actual_subvolumes'] = Selector(str(_("Actual Btrfs Subvolumes")),
									enabled=True)
			self._menu_options['uuid'] = Selector(str(_("uuid")),
								enabled=True)

		self._menu_options['save'] = Selector(str(_('Save')),
													exec_func=lambda n, v: self._check_coherence(),
													enabled=True)
		self._menu_options['cancel'] = Selector(str(_('Cancel')),
												func=lambda pre: True,
												exec_func=lambda n, v: self.fast_exit(n),
												enabled=True)
		self.cancel_action = 'cancel'
		self.save_action = 'save'

		self.bottom_list = [self.save_action, self.cancel_action]

	def fast_exit(self, action) -> bool:
		""" an exec_func attached to the cancel action to avoid mandatory field checking"""
		if self.option(action).get_selection():
			for item in self.list_options():
				if self.option(item).is_mandatory():
					self.option(item).set_mandatory(False)
		return True

	def _check_coherence(self) -> bool:
		""" we check if the resultimg partition slot has coherent values and can be exited"""
		status = True
		forgettable = True
		msg_lines = [str(_("We have found following problems at your setup"))]
		# we always check for space no matter what happens
		min_size = 1
		if self.ds['location'].size <= min_size:  # TODO whatever minimum size you want
			msg_lines.append(str(_("Location must have a minimal size of {}").format(min_size)))
			forgettable = False
			status = False
		elif self._original_data == self.ds:
			return True

		if not self.ds['filesystem'] and self.ds['type'].lower() == 'primary':  # TODO check for MBR
			msg_lines.append(str(_("Partition SHOULD have a filesystem ")))
			status = False

		if not (self.ds['mountpoint'] or self.ds['subvolumes']) and self.ds['filesystem']:
			msg_lines.append(str(_("Partition SHOULD have a mountpoint or mounted subvolumes")))
			status = False

		if self.ds['boot'] and self.disk.type.upper() == 'GPT':
			if self.ds['filesystem'].upper() not in ('FAT32','VFAT'):
				msg_lines.append(str(_("Boot partitions on GPT drives must be FAT32")))
				forgettable = False
				status = False

		if self.ds['filesystem'] == 'btrfs':
			if self.ds['mountpoint'] and [entry.mountpoint for entry in self.ds['subvolumes'] if entry.mountpoint]:
				msg_lines.append(str(_("Btrfs partitions with subvolumes MUST NOT be mounted boot at root level and in subvolumes")))
				forgettable = False
				status = False

		if not status:
			errors = '\n - '.join(msg_lines)
			if forgettable:
				status = self._generic_boolean_editor(str(_('Errors found: \n{} Do you want to proceed anyway?').format(errors)),False)
			else:
				log(errors,fg="red")
				print(_("press any key to exit"))
				input()
		return status

	def exit_callback(self):
		""" end processing """
		# we exit without moving data
		if self.option(self.cancel_action).get_selection():
			return
		# if no location is given we abort
		if self.ds.get('location') is None:
			return
		self._conversion_to_object()

	def _generic_string_editor(self, prompt: str, prev: Any) -> str:
		return TextInput(prompt, prev).run()

	def _generic_boolean_editor(self, prompt:str, prev: bool) -> bool:
		if prev:
			base_value = 'yes'
		else:
			base_value = 'no'
		response = Menu(prompt, ['yes', 'no'], preset_values=base_value).run()
		if response.value == 'yes':
			return True
		else:
			return False

	def _show_location(self, location: StorageSlot) -> str:
		""" a pretty way to show the location at the menu"""
		return f"start {location.startInput}, size {location.sizeInput} ({location.sizeN})"

	def _select_boot(self, prev: bool) -> bool:
		""" set the bool property """
		# TODO this checks and changes ought  to be done at the end of processing
		value = self._generic_boolean_editor(str(_('Set bootable partition :')), prev)
		# only a boot per disk is allowed
		if value and self._list:
			bootable = [entry for entry in self.disk.partition_list(self._list) if entry.boot]
			if len(bootable) > 0:
				log(_('There exists another bootable partition on disk. Unset it before defining this one'))
				if self.disk.type.upper() == 'GPT':
					log(_('On GPT drives ensure that the boot partition is an EFI partition'))
				print(_("press any key to continue"))
				input()
				return prev
		# TODO It's a bit more complex than that. This is only for GPT drives
		if value and self.disk.type.upper() == 'GPT':
			self.option('mountpoint').set_current_selection('/boot')
			self.option('filesystem').set_current_selection('FAT32')
			self.option('encrypted').set_current_selection(False)
			self.option('type').set_current_selection('EFI')
		return value

	def _select_encryption(self, prev: bool) -> str:
		""" select encrption status. Gpt drives CAN NOT have an encrypted boot """
		if self.disk.type.upper() == 'GPT' and self.ds['boot']:
			return False
		return self._generic_boolean_editor(str(_('Set encryption status :')), prev)

	def _select_filesystem(self, prev: str) -> str:
		""" set the filesystem property"""
		fstype_title = _('Enter a desired filesystem type for the partition: ')
		fstype = Menu(fstype_title, fs_types(), skip=False, preset_values=prev).run()
		if not fstype.value:
			return None
		# changed FS means reformat
		if fstype.value != self._original_data.get('filesystem',''):
			self.option('wipe').set_current_selection(True)

		if fstype.value == 'btrfs':
			self.option('subvolumes').set_enabled(True)
		else:
			self.option('subvolumes').set_enabled(False)
		return fstype.value

	# this block is for assesing space allocation. probably it ougth to be taken off the class
	def _get_gaps_in_disk(self, list_to_check: List[StorageSlot]) -> List[StorageSlot]:
		""" get which gaps are in the disk """
		if list_to_check is None:
			tmp_list = hw_discover([self.disk.device])
			return self._get_gaps_in_disk(tmp_list)
		elif len(list_to_check) == 0:
			return []
		else:
			tmp_list = [part for part in self.disk.partition_list(list_to_check) if part != self.data]
			return self.disk.gap_list(tmp_list)

	def _get_current_gap_pos(self, gap_list: List[StorageSlot], need: StorageSlot) -> int:
		""" we get the index of the gap where the proposed allocation (need) is """
		if not need.start or need.start < 0:
			return None
		for i, gap in enumerate(gap_list):

			if gap.start <= need.start < gap.end:
				return i
		return None

	def _adjust_size(self, original: StorageSlot, need: StorageSlot):
		""" we reasses the size of need after the start position is changed. Original holds the value before the change"""
		if str(need.sizeInput).strip().endswith('%'):
			need.sizeInput = original.sizeInput
		newsize = need.size - (need.start - original.start)
		need.sizeInput = units_from_model(newsize, original.sizeInput)

	def _show_gaps(self, gap_list: List[StorageSlot]):
		""" for header
		purposes """
		screen_data = FormattedOutput.as_table(gap_list, 'as_dict', ['start', 'end', 'size', 'sizeN'])
		print('Current free space is')
		print(screen_data)

	def _ask_for_start(self, gap_list: List[StorageSlot], need: StorageSlot) -> str:
		""" all the code needed for the user setting a start position
		returns a string with the operation status quit/repeat/None
		the size is returned at need object"""
		pos = self._get_current_gap_pos(gap_list, need)
		original = copy(need)
		print(f"Current allocation need is start:{need.pretty_print('start')} size {need.pretty_print('size')}")
		if pos:
			prompt = _("Define a start sector for the partition. Enter a value or \n"
					"c to get the first sector of the current slot \n"
					"q to quit \n"
					"==> ")
			starts = need.startInput
			starts = TextInput(prompt, starts).run()
			if starts == 'q':
				need = original
				return 'quit'
			elif starts == 'c':
				starts = gap_list[pos].startInput
		else:
			prompt = _("Define a start sector for the partition. Enter a value or \n"
					"f to get the first sector of the first free slot which can hold a partition\n"
					"l to get the first sector of the last free slot \n"
					"q to quit \n"
					"==> ")
			starts = need.startInput
			starts = TextInput(prompt, starts).run()
			if starts == 'q':
				return 'quit'
			elif starts == 'f':
				starts = gap_list[0].startInput  # TODO 32 o 4K
				pos = 0
			elif starts == 'l':
				starts = gap_list[-1].startInput
				pos = len(gap_list) - 1

		need.startInput = starts
		pos = self._get_current_gap_pos(gap_list, need)
		if pos is None:
			print(f"Requested start position {need.pretty_print('start')}not in an avaliable slot. Try again")
			need.startInput = original.startInput
			return 'repeat'
		if gap_list[pos].start <= need.start < gap_list[pos].end:
			self._adjust_size(original, need)
			return None

	def _ask_for_size(self, gap_list: List[StorageSlot], need: StorageSlot) -> str:
		""" all the code needed for the user setting a size for the partition
		returns a string with the operation status quit/repeat/None
		the size is returned at need object"""
		# TODO optional ... ask for size confirmation
		original = copy(need)
		print(f"Current allocation need is start:{need.pretty_print('start')} size {need.pretty_print('size')}")
		pos = self._get_current_gap_pos(gap_list, need)
		if pos is not None:
			maxsize = gap_list[pos].end - need.start + 1
			maxsizeN = unit_best_fit(maxsize, 's')
			prompt = _("Define a size for the partition max {}\n \
		as a quantity (with units at the end) or a percentaje of the free space (ends with %),\n \
		or q to quit \n ==> ").format(f"{maxsize} s. ({maxsizeN})")

			sizes = need.sizeInput
			sizes = TextInput(prompt, sizes).run()
			sizes = sizes.strip()
			if sizes.lower() == 'q':
				need = original
				return 'quit'
			if sizes.endswith('%'):
				# TODO from gap percentage to disk percentage
				pass
			need.sizeInput = sizes
			if need.size > maxsize:
				print(_('Size {} exceeds the maximum size {}').format(need.pretty_print('size'), f"{maxsize} s. ({maxsizeN})"))
				need = original
				return 'repeat'
			return None
		else:
			return 'quit'

	def _select_physical(self, prev: StorageSlot) -> StorageSlot:
		""" frontend for all the code needed to allocate the partition"""
		# from os import system
		# an existing partition can not be physically changed
		if self.data.uuid:
			return prev
		# TODO The gap list should respect alignment and minimum size
		gap_list = self._get_gaps_in_disk(self._list)
		my_need = copy(prev)
		while True:
			system('clear')
			self._show_gaps(gap_list)
			action = 'begin'
			while action:
				my_need = copy(prev)  # I think i don't need a deepcopy
				action = self._ask_for_start(gap_list, my_need)
				if action == 'quit':
					return prev
			action = 'begin'
			while action:
				my_need_full = copy(my_need)
				action = self._ask_for_size(gap_list, my_need_full)
				if action == 'quit':
					return prev
			# changed size implies wipe (won't even try to resize partitions
			if my_need_full != self._original_data['location']:
				self.option('wipe').set_current_selection(True)
			return my_need_full

	def _manage_subvolumes(self, prev: Any) -> SubvolumeList:
		if self.option('filesystem').get_selection() != 'btrfs':
			return []
		if prev is None:
			prev = []
		return SubvolumeList(_("Manage btrfs subvolumes for current partition"), prev).run()
