from __future__ import annotations

import ipaddress
import logging
from typing import Any, Optional, TYPE_CHECKING, List, Union

from ..menu.menu import MenuSelectionType
from ..menu.text_input import TextInput
from ..models.network_configuration import NetworkConfiguration, NicType

from ..networking import list_interfaces
from ..menu import Menu
from ..output import log
from ..menu.list_manager import ListManager

if TYPE_CHECKING:
	_: Any


class ManualNetworkConfig(ListManager):
	"""
	subclass of ListManager for the managing of network configuration accounts
	"""

	def __init__(self, prompt: str, ifaces: Union[None, NetworkConfiguration, List[NetworkConfiguration]]):
		"""
		param: prompt
		type: str
		param: ifaces already defined previously
		type: Dict
		"""

		if ifaces is not None and isinstance(ifaces, list):
			display_values = {iface.iface: iface for iface in ifaces}
		else:
			display_values = {}

		self._action_add = str(_('Add interface'))
		self._action_edit = str(_('Edit interface'))
		self._action_delete = str(_('Delete interface'))

		self._iface_actions = [self._action_edit, self._action_delete]

		super().__init__(prompt, display_values, self._iface_actions, self._action_add)

	def run_manual(self) -> List[NetworkConfiguration]:
		ifaces = super().run()
		if ifaces is not None:
			return list(ifaces.values())
		return []

	def exec_action(self, data: Any):
		if self.action == self._action_add:
			iface_name = self._select_iface(data.keys())
			if iface_name:
				iface = NetworkConfiguration(NicType.MANUAL, iface=iface_name)
				data[iface_name] = self._edit_iface(iface)
		elif self.target:
			iface_name = list(self.target.keys())[0]
			iface = data[iface_name]

			if self.action == self._action_edit:
				data[iface_name] = self._edit_iface(iface)
			elif self.action == self._action_delete:
				del data[iface_name]

		return data

	def _select_iface(self, existing_ifaces: List[str]) -> Optional[Any]:
		all_ifaces = list_interfaces().values()
		available = set(all_ifaces) - set(existing_ifaces)
		choice = Menu(str(_('Select interface to add')), list(available), skip=True).run()

		if choice.type_ == MenuSelectionType.Esc:
			return None

		return choice.value

	def _edit_iface(self, edit_iface :NetworkConfiguration):
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
				gateway_input = TextInput(_('Enter your gateway (router) IP address or leave blank for none: '),
									edit_iface.gateway).run().strip()
				try:
					if len(gateway_input) > 0:
						ipaddress.ip_address(gateway_input)
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


def ask_to_configure_network(preset: Union[None, NetworkConfiguration, List[NetworkConfiguration]]) -> Optional[Union[List[NetworkConfiguration], NetworkConfiguration]]:
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
		explode_on_interrupt=True,
		explode_warning=warning
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
		manual = ManualNetworkConfig('Configure interfaces', preset)
		return manual.run_manual()

	return preset
