# from __future__ import annotations
#
# import re
# from pathlib import Path
# from typing import Any, TYPE_CHECKING, List, Optional, Dict, Tuple
#
# from .subvolume_menu import SubvolumeMenu
# from .device_handler import device_handler
# from .device_model import (
# 	PartitionModification, LvmConfiguration, DeviceModification, ModificationStatus,
# 	LvmLayoutType, LvmVolumeGroup, LvmVolume, FilesystemType, LvmVolumeStatus, Size,
# 	Unit
# )
# from ..menu import (
# 	TableMenu, MenuSelectionType, TextInput, AbstractSubMenu, Selector, ListManager,
# 	Menu, MenuSelection
# )
# from ..output import FormattedOutput, warn
#
# if TYPE_CHECKING:
# 	_: Any
#
#
# class LvmVolumeList(ListManager):
#
# 	def __init__(
# 		self,
# 		prompt: str,
# 		device_mods: List[DeviceModification],
# 		lvm_vol_group: LvmVolumeGroup,
# 		lvm_volumes: Optional[List[LvmVolume]]
# 	):
# 		self._actions = {
# 			'create_new_volume': str(_('Create a new volume')),
# 			# 'suggest_partition_layout': str(_('Suggest partition layout')),
# 			'remove_added_volumes': str(_('Remove all newly added volumes')),
# 			'assign_mountpoint': str(_('Assign mountpoint')),
# 			'mark_formatting': str(_('Mark/Unmark to be formatted (wipes data)')),
# 			'set_filesystem': str(_('Change filesystem')),
# 			'btrfs_mark_compressed': str(_('Mark/Unmark as compressed')),  # btrfs only
# 			'btrfs_set_subvolumes': str(_('Set subvolumes')),  # btrfs only
# 			'delete_partition': str(_('Delete volume'))
# 		}
#
# 		self._device_mods = device_mods
# 		self._lvm_vol_group = lvm_vol_group
#
# 		display_actions = list(self._actions.values())
# 		lvm_volumes = lvm_volumes if lvm_volumes else []
# 		super().__init__(prompt, lvm_volumes, display_actions[:2], display_actions[3:])
#
# 	def selected_action_display(self, partition: LvmVolume) -> str:
# 		return str(_('Partition'))
#
# 	def filter_options(self, selection: LvmVolume, options: List[str]) -> List[str]:
# 		not_filter = []
#
# 		# only display formatting if the volume exists already
# 		if not selection.exists():
# 			not_filter += [self._actions['mark_formatting']]
# 		else:
# 			# only allow these options if the existing volume
# 			# was marked as formatting, otherwise we run into issues where
# 			# 1. select a new fs -> potentially mark as wipe now
# 			# 2. Switch back to old filesystem -> should unmark wipe now, but
# 			#     how do we know it was the original one?
# 			not_filter += [
# 				self._actions['set_filesystem'],
# 				self._actions['assign_mountpoint'],
# 				self._actions['btrfs_mark_compressed'],
# 				self._actions['btrfs_set_subvolumes']
# 			]
#
# 		# non btrfs volume shouldn't get btrfs options
# 		if selection.fs_type != FilesystemType.Btrfs:
# 			not_filter += [self._actions['btrfs_mark_compressed'], self._actions['btrfs_set_subvolumes']]
# 		else:
# 			not_filter += [self._actions['assign_mountpoint']]
#
# 		return [o for o in options if o not in not_filter]
#
# 	def handle_action(
# 		self,
# 		action: str,
# 		entry: Optional[LvmVolume],
# 		data: List[LvmVolume]
# 	) -> List[LvmVolume]:
# 		action_key = [k for k, v in self._actions.items() if v == action][0]
#
# 		match action_key:
# 			case 'create_new_volume':
# 				new_volume = self._create_new_volume()
# 				data += [new_volume]
# 			# case 'suggest_partition_layout':
# 			# 	new_partitions = self._suggest_partition_layout(data)
# 			# 	if len(new_partitions) > 0:
# 			# 		data = new_partitions
# 			case 'remove_added_volumes':
# 				choice = self._reset_confirmation()
# 				if choice.value == Menu.yes():
# 					data = [part for part in data if part.is_exists_or_modify()]
# 			case 'assign_mountpoint' if entry:
# 				entry.mountpoint = self._prompt_mountpoint()
# 			case 'mark_formatting' if entry:
# 				self._prompt_formatting(entry)
# 			case 'set_filesystem' if entry:
# 				fs_type = self._prompt_volume_fs_type()
# 				if fs_type:
# 					entry.fs_type = fs_type
# 					# btrfs subvolumes will define mountpoints
# 					if fs_type == FilesystemType.Btrfs:
# 						entry.mountpoint = None
# 			case 'btrfs_mark_compressed' if entry:
# 				self._set_compressed(entry)
# 			case 'btrfs_set_subvolumes' if entry:
# 				self._set_btrfs_subvolumes(entry)
# 			case 'delete_partition' if entry:
# 				data = self._delete_partition(entry, data)
#
# 		return data
#
# 	def _delete_partition(
# 		self,
# 		entry: LvmVolume,
# 		data: List[LvmVolume]
# 	) -> List[LvmVolume]:
# 		if entry.is_exists_or_modify():
# 			entry.status = LvmVolumeStatus.Delete
# 			return data
# 		else:
# 			return [d for d in data if d != entry]
#
# 	def _set_compressed(self, volume: LvmVolume):
# 		compression = 'compress=zstd'
#
# 		if compression in volume.mount_options:
# 			volume.mount_options = [o for o in volume.mount_options if o != compression]
# 		else:
# 			volume.mount_options.append(compression)
#
# 	def _set_btrfs_subvolumes(self, volume: LvmVolume):
# 		volume.btrfs_subvols = SubvolumeMenu(
# 			_("Manage btrfs subvolumes for current volume"),
# 			volume.btrfs_subvols
# 		).run()
#
# 	def _prompt_formatting(self, volume: LvmVolume):
# 		# an existing volume can toggle between Exist or Modify
# 		if volume.is_modify():
# 			volume.status = LvmVolumeStatus.Exist
# 			return
# 		elif volume.exists():
# 			volume.status = LvmVolumeStatus.Modify
#
# 	def _prompt_mountpoint(self) -> Path:
# 		header = '{}\n'.format(
# 			str(_('Volume mount-points are relative to inside the installation, the root would be / as an example.'))
# 		)
# 		prompt = str(_('Mountpoint: '))
#
# 		print(header)
#
# 		while True:
# 			value = TextInput(prompt).run().strip()
#
# 			if value:
# 				mountpoint = Path(value)
# 				break
#
# 		return mountpoint
#
# 	def _prompt_volume_fs_type(self) -> FilesystemType:
# 		options = {fs.value: fs for fs in FilesystemType if fs != FilesystemType.Crypto_luks}
#
# 		prompt = '{}'.format(str(_('Enter a desired filesystem type for the volume')))
# 		choice = Menu(prompt, options, sort=False, skip=False).run()
# 		return options[choice.single_value]
#
# 	def _validate_value(
# 		self,
# 		sector_size: Size,
# 		total_size: Size,
# 		value: str
# 	) -> Optional[Size]:
# 		match = re.match(r'([0-9]+)([a-zA-Z|%]*)', value, re.I)
#
# 		if match:
# 			value, unit = match.groups()
#
# 			if unit == '%':
# 				unit = Unit.Percent.name
#
# 			if unit and unit not in Unit.get_all_units():
# 				return None
#
# 			unit = Unit[unit] if unit else Unit.sectors
# 			return Size(int(value), unit, sector_size, total_size)
#
# 		return None
#
# 	def _enter_size(
# 		self,
# 		sector_size: Size,
# 		total_size: Size,
# 		prompt: str
# 	) -> Size:
# 		while True:
# 			value = TextInput(prompt).run().strip()
#
# 			if not value:
# 				continue
#
# 			if size := self._validate_value(sector_size, total_size, value):
# 				return size
#
# 			warn(f'Invalid value: {value}')
#
# 	def _prompt_size(self) -> Tuple[Size, Size]:
# 		lvm_pvs = self._lvm_vol_group.pvs
# 		lvm_pvs_table = FormattedOutput.as_table(lvm_pvs)
#
# 		sector_size = self._device_mods[0].device.device_info.sector_size
#
# 		total_size = sum([pv.length for pv in lvm_pvs], Size(0, Unit.B))
# 		total_sectors = total_size.format_size(Unit.sectors, sector_size)
# 		total_bytes = total_size.format_size(Unit.B)
#
# 		prompt = '{}\n\n{}\n{}\n\n{}\n{}\n'.format(
# 			str(_('Currently associated PVs in the VG')),
# 			lvm_pvs_table,
# 			str(_('Total: {} / {}')).format(total_sectors, total_bytes),
# 			str(_('All entered values can be suffixed with a unit: B, KB, KiB, MB, MiB...')),
# 			str(_('If no unit is provided, the value is interpreted as sectors'))
# 		)
#
# 		print(prompt)
#
# 		# prompt until a valid start sector was entered
# 		start_size = self._enter_size(
# 			sector_size,
# 			total_size,
# 			str(_('Enter start: '))
# 		)
#
# 		# prompt until valid end sector was entered
# 		end_size = self._enter_size(
# 			sector_size,
# 			total_size,
# 			str(_('Enter end: '))
# 		)
#
# 		return start_size, end_size
#
# 	def _create_new_volume(self) -> LvmVolume:
# 		title = '\n{}: '.format(str(_('Volume name')))
# 		vol_name = TextInput(title).run()
#
# 		fs_type = self._prompt_volume_fs_type()
#
# 		start_size, end_size = self._prompt_size()
# 		length = end_size - start_size
#
# 		# new line for the next prompt
# 		print()
#
# 		mountpoint = None
# 		if fs_type != FilesystemType.Btrfs:
# 			mountpoint = self._prompt_mountpoint()
#
# 		volume = LvmVolume(
# 			status=LvmVolumeStatus.Create,
# 			name=vol_name,
# 			fs_type=fs_type,
# 			start=start_size,
# 			length=length,
# 			mountpoint=mountpoint
# 		)
#
# 		return volume
#
# 	def _reset_confirmation(self) -> MenuSelection:
# 		prompt = str(_('This will remove all newly added volumes, continue?'))
# 		choice = Menu(prompt, Menu.yes_no(), default_option=Menu.no(), skip=False).run()
# 		return choice
#
# 	# def _suggest_partition_layout(self, data: List[PartitionModification]) -> List[PartitionModification]:
# 	# 	# if modifications have been done already, inform the user
# 	# 	# that this operation will erase those modifications
# 	# 	if any([not entry.exists() for entry in data]):
# 	# 		choice = self._reset_confirmation()
# 	# 		if choice.value == Menu.no():
# 	# 			return []
# 	#
# 	# 	from ..interactions.disk_conf import suggest_single_disk_layout
# 	#
# 	# 	device_modification = suggest_single_disk_layout(self._device)
# 	# 	return device_modification.partitions
#
#
# class LvmConfigurationMenu(AbstractSubMenu):
# 	def __init__(
# 		self,
# 		lvm_config: Optional[LvmConfiguration],
# 		data_store: Dict[str, Any],
# 		device_mods: List[DeviceModification] = []
# 	):
# 		self._lvm_config = lvm_config
# 		self._device_mods = device_mods
#
# 		super().__init__(data_store=data_store)
#
# 	def setup_selection_menu_options(self):
# 		self._menu_options['lvm_pvs'] = \
# 			Selector(
# 				_('Physical volumes'),
# 				lambda x: self._select_lvm_pvs(x),
# 				display_func=lambda x: self.defined_text if x else '',
# 				preview_func=self._prev_lvm_pv,
# 				default=self._lvm_config.lvm_pvs if self._lvm_config else [],
# 				enabled=True
# 			)
# 		self._menu_options['lvm_vol_group'] = \
# 			Selector(
# 				_('Volume group'),
# 				lambda x: self._select_lvm_vol_group(x),
# 				display_func=lambda x: self.defined_text if x else '',
# 				preview_func=self._prev_lvm_vol_group,
# 				default=self._lvm_config.vol_groups if self._lvm_config else [],
# 				dependencies=['lvm_pvs'],
# 				enabled=True
# 			)
# 		self._menu_options['lvm_volumes'] = \
# 			Selector(
# 				_('Volumes'),
# 				lambda x: self._select_lvm_volumes(x),
# 				display_func=lambda x: self.defined_text if x else '',
# 				preview_func=self._prev_lvm_volumes,
# 				default=self._lvm_config.volumes if self._lvm_config else [],
# 				dependencies=['lvm_vol_group'],
# 				enabled=True
# 			)
#
# 	def run(self, allow_reset: bool = True) -> Optional[LvmConfiguration]:
# 		super().run(allow_reset=allow_reset)
#
# 		lvm_pvs: Optional[List[PartitionModification]] = self._data_store.get('lvm_pvs', None)
# 		lvm_vol_group: Optional[LvmVolumeGroup] = self._data_store.get('lvm_vol_group', None)
# 		lvm_volumes: Optional[List[LvmVolume]] = self._data_store.get('lvm_volumes', None)
#
# 		if lvm_pvs and lvm_vol_group and lvm_volumes:
# 			return LvmConfiguration(
# 				config_type=LvmLayoutType.Manual,
# 				lvm_pvs=lvm_pvs,
# 				vol_groups=lvm_vol_group,
# 				volumes=lvm_volumes
# 			)
#
# 		return None
#
# 	def _select_lvm_pvs(
# 		self,
# 		preset: Optional[List[PartitionModification]],
# 	) -> Optional[List[PartitionModification]]:
# 		lvm_pvs = select_lvm_pvs(preset, self._device_mods)
#
# 		if lvm_pvs != preset:
# 			self._menu_options['lvm_vol_group'].set_current_selection(None)
# 			self._menu_options['lvm_volumes'].set_current_selection(None)
#
# 		return lvm_pvs
#
# 	def _select_lvm_vol_group(self, preset: Optional[LvmVolumeGroup]) -> Optional[LvmVolumeGroup]:
# 		lvm_pvs: Optional[List[PartitionModification]] = self._menu_options['lvm_pvs'].current_selection
# 		if lvm_pvs:
# 			return select_lvm_vol_group(preset, lvm_pvs)
# 		return preset
#
# 	def _select_lvm_volumes(self, preset: Optional[List[LvmVolume]]):
# 		lvm_vol_group: Optional[LvmVolumeGroup] = self._menu_options['lvm_vol_group'].current_selection
# 		if lvm_vol_group:
# 			lvm_volumes = LvmVolumeList('', self._device_mods, lvm_vol_group, preset).run()
# 			return lvm_volumes
#
# 		return preset
#
# 	def _prev_lvm_pv(self) -> Optional[str]:
# 		lvm_pvs: Optional[List[PartitionModification]] = self._menu_options['lvm_pvs'].current_selection
#
# 		if lvm_pvs:
# 			return FormattedOutput.as_table(lvm_pvs)
#
# 		return None
#
# 	def _prev_lvm_vol_group(self) -> Optional[str]:
# 		lvm_vol_group: Optional[LvmVolumeGroup] = self._menu_options['lvm_vol_group'].current_selection
#
# 		if lvm_vol_group:
# 			output = '{}: {}\n\n'.format(str(_('Volume group')), lvm_vol_group.name)
# 			output += FormattedOutput.as_table(lvm_vol_group.pvs)
# 			return output
#
# 		return None
#
# 	def _prev_lvm_volumes(self) -> Optional[str]:
# 		lvm_volumes: Optional[List[LvmVolume]] = self._menu_options['lvm_volumes'].current_selection
#
# 		if lvm_volumes:
# 			output = FormattedOutput.as_table(lvm_volumes)
# 			return output
#
# 		return None
#
#
# def _determine_pv_selection(
# 	device_mods: List[DeviceModification] = []
# ) -> List[PartitionModification]:
# 	"""
# 	We'll be determining which partitions to display for the PV
# 	selection; to make the configuration as flexible as possible
# 	we'll use all existing partitions and then apply the
# 	configuration partition configurations on top
# 	"""
# 	options: List[PartitionModification] = []
#
# 	# add all existing partitions known to the world
# 	for device in device_handler.devices:
# 		dev = device_handler.get_device(device.device_info.path)
# 		if dev and dev.partition_infos:
# 			for partition in dev.partition_infos:
# 				part_mod = PartitionModification.from_existing_partition(partition)
# 				options.append(part_mod)
#
# 	for dev_mod in device_mods:
# 		# remove all partitions that would be wiped
# 		if dev_mod.wipe:
# 			options = list(filter(lambda x: x.part_info not in dev_mod.device.partition_infos, options))
#
# 		for part_mod in dev_mod.partitions:
# 			match part_mod.status:
# 				case ModificationStatus.Exist:
# 					# should already be in the list
# 					pass
# 				case ModificationStatus.Create:
# 					options.append(part_mod)
# 				case ModificationStatus.Delete:
# 					options = list(filter(lambda x: x != part_mod.part_info, options))
# 				case ModificationStatus.Modify:
# 					options = list(filter(lambda x: x != part_mod.part_info, options))
# 					options.append(part_mod)
#
# 	return options
#
#
# def select_lvm_pvs(
# 	preset: Optional[List[PartitionModification]] = [],
# 	device_mods: List[DeviceModification] = []
# ) -> Optional[List[PartitionModification]]:
# 	title = str(_('Select the devices to use as physical volumes (PV)'))
# 	warning = str(_('If you reset the device selection then the entire LVM configuration will be reset. Are you sure?'))
#
# 	options = _determine_pv_selection(device_mods)
#
# 	preset_values = preset if preset else []
#
# 	choice = TableMenu(
# 		title,
# 		data=options,
# 		multi=True,
# 		preset=preset_values,
# 		allow_reset=True,
# 		allow_reset_warning_msg=warning
# 	).run()
#
# 	match choice.type_:
# 		case MenuSelectionType.Skip: return preset
# 		case MenuSelectionType.Reset: return None
# 		case MenuSelectionType.Selection: return choice.multi_value
#
# 	return preset
#
#
# def select_lvm_vol_group(
# 	preset: Optional[LvmVolumeGroup],
# 	options: List[PartitionModification]
# ) -> Optional[LvmVolumeGroup]:
# 	prompt = str(_('Enter a volume group name')) + ': '
# 	preset_val = preset.name if preset else ''
# 	group_name = TextInput(prompt, prefilled_text=preset_val).run()
#
# 	if not group_name:
# 		return preset
#
# 	title = '{}: {}'.format(str(_('Select the devices to be associated with the volume group')), group_name)
# 	preset_choices = preset.pvs if preset else []
#
# 	choice = TableMenu(
# 		title,
# 		data=options,
# 		multi=True,
# 		preset=preset_choices,
# 		allow_reset=True,
# 		skip=False
# 	).run()
#
# 	match choice.type_:
# 		case MenuSelectionType.Reset: return None
# 		case MenuSelectionType.Skip: return preset
# 		case MenuSelectionType.Selection:
# 			return LvmVolumeGroup(
# 				group_name,
# 				choice.multi_value
# 			)
#
# 	return preset
