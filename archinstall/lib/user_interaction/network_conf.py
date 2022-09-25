from __future__ import annotations

import ipaddress
import logging
from typing import Any, Optional, TYPE_CHECKING, List, Union, Dict

from ..menu.menu import MenuSelectionType
from ..menu.text_input import TextInput
from ..models.network_configuration import NetworkConfiguration, NicType

from ..networking import list_interfaces
from ..menu import Menu
from ..output import log, FormattedOutput
from ..menu.list_manager import ListManager

if TYPE_CHECKING:
	_: Any


class ManualNetworkConfig(ListManager):
	"""
	subclass of ListManager for the managing of network configurations
	"""

	def __init__(self, prompt: str, ifaces: List[NetworkConfiguration]):
		self._actions = [
			str(_('Add interface')),
			str(_('Edit interface')),
			str(_('Delete interface'))
		]

		super().__init__(prompt, ifaces, [self._actions[0]], self._actions[1:])

	def reformat(self, data: List[NetworkConfiguration]) -> Dict[str, Optional[NetworkConfiguration]]:
		table = FormattedOutput.as_table(data)
		rows = table.split('\n')

		# these are the header rows of the table and do not map to any User obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		display_data: Dict[str, Optional[NetworkConfiguration]] = {f'  {rows[0]}': None, f'  {rows[1]}': None}

		for row, iface in zip(rows[2:], data):
			row = row.replace('|', '\\|')
			display_data[row] = iface

		return display_data

	def selected_action_display(self, iface: NetworkConfiguration) -> str:
		return iface.iface if iface.iface else ''

	def handle_action(self, action: str, entry: Optional[NetworkConfiguration], data: List[NetworkConfiguration]):
		if action == self._actions[0]:  # add
			iface_name = self._select_iface(data)
			if iface_name:
				iface = NetworkConfiguration(NicType.MANUAL, iface=iface_name)
				iface = self._edit_iface(iface)
				data += [iface]
		elif entry:
			if action == self._actions[1]:  # edit interface
				data = [d for d in data if d.iface != entry.iface]
				data.append(self._edit_iface(entry))
			elif action == self._actions[2]:  # delete
				data = [d for d in data if d != entry]

		return data

	def _select_iface(self, data: List[NetworkConfiguration]) -> Optional[Any]:
		all_ifaces = list_interfaces().values()
		existing_ifaces = [d.iface for d in data]
		available = set(all_ifaces) - set(existing_ifaces)
		choice = Menu(str(_('Select interface to add')), list(available), skip=True).run()

		if choice.type_ == MenuSelectionType.Esc:
			return None

		return choice.value

	def _edit_iface(self, edit_iface: NetworkConfiguration):
		iface_name = edit_iface.iface
		modes = ['DHCP (auto detect)', 'IP (static)']
		default_mode = 'DHCP (auto detect)'

		prompt = _('Select which mode to configure for "{}" or skip to use default mode "{}"').format(iface_name, default_mode)
		mode = Menu(prompt, modes, default_option=default_mode, skip=False).run()

		if mode.value == 'IP (static)':
			while 1:
				prompt = _('Enter the IP and subnet for {} (example: 192.168.0.5/24): ').format(iface_name)
				ip = TextInput(prompt, edit_iface.ip).run().strip()
				# Implemented new check for correct IP/subnet input
				try:
					ipaddress.ip_interface(ip)
					break
				except ValueError:
					log("You need to enter a valid IP in IP-config mode.", level=logging.WARNING, fg='red')

			# Implemented new check for correct gateway IP address
			gateway = None

			while 1:
				gateway = TextInput(
					_('Enter your gateway (router) IP address or leave blank for none: '),
					edit_iface.gateway
				).run().strip()
				try:
					if len(gateway) > 0:
						ipaddress.ip_address(gateway)
					break
				except ValueError:
					log("You need to enter a valid gateway (router) IP address.", level=logging.WARNING, fg='red')

			if edit_iface.dns:
				display_dns = ' '.join(edit_iface.dns)
			else:
				display_dns = None
			dns_input = TextInput(_('Enter your DNS servers (space separated, blank for none): '), display_dns).run().strip()

			dns = []
			if len(dns_input):
				dns = dns_input.split(' ')

			return NetworkConfiguration(NicType.MANUAL, iface=iface_name, ip=ip, gateway=gateway, dns=dns, dhcp=False)
		else:
			# this will contain network iface names
			return NetworkConfiguration(NicType.MANUAL, iface=iface_name)


def ask_to_configure_network(
	preset: Union[NetworkConfiguration, List[NetworkConfiguration]]
) -> Optional[NetworkConfiguration | List[NetworkConfiguration]]:
	"""
		Configure the network on the newly installed system
	"""
	network_options = {
		'none': str(_('No network configuration')),
		'iso_config': str(_('Copy ISO network configuration to installation')),
		'network_manager': str(_('Use NetworkManager (necessary to configure internet graphically in GNOME and KDE)')),
		'manual': str(_('Manual configuration'))
	}
	# for this routine it's easier to set the cursor position rather than a preset value
	cursor_idx = None

	if preset and not isinstance(preset, list):
		if preset.type == 'iso_config':
			cursor_idx = 0
		elif preset.type == 'network_manager':
			cursor_idx = 1

	warning = str(_('Are you sure you want to reset this setting?'))

	choice = Menu(
		_('Select one network interface to configure'),
		list(network_options.values()),
		cursor_index=cursor_idx,
		sort=False,
		raise_error_on_interrupt=True,
		raise_error_warning_msg=warning
	).run()

	match choice.type_:
		case MenuSelectionType.Esc: return preset
		case MenuSelectionType.Ctrl_c: return None

	if choice.value == network_options['none']:
		return None
	elif choice.value == network_options['iso_config']:
		return NetworkConfiguration(NicType.ISO)
	elif choice.value == network_options['network_manager']:
		return NetworkConfiguration(NicType.NM)
	elif choice.value == network_options['manual']:
		preset_ifaces = preset if isinstance(preset, list) else []
		return ManualNetworkConfig('Configure interfaces', preset_ifaces).run()

	return preset
