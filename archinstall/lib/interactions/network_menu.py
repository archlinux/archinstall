from __future__ import annotations

import ipaddress
from typing import Any, Optional, TYPE_CHECKING, List, Dict

from ..menu import MenuSelectionType, TextInput
from ..models.network_configuration import NetworkConfiguration, NicType, Nic

from ..networking import list_interfaces
from ..output import FormattedOutput, warn
from ..menu import ListManager, Menu

if TYPE_CHECKING:
	_: Any


class ManualNetworkConfig(ListManager):
	"""
	subclass of ListManager for the managing of network configurations
	"""

	def __init__(self, prompt: str, preset: List[Nic]):
		self._actions = [
			str(_('Add interface')),
			str(_('Edit interface')),
			str(_('Delete interface'))
		]
		super().__init__(prompt, preset, [self._actions[0]], self._actions[1:])

	def reformat(self, data: List[Nic]) -> Dict[str, Optional[Nic]]:
		table = FormattedOutput.as_table(data)
		rows = table.split('\n')

		# these are the header rows of the table and do not map to any User obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		display_data: Dict[str, Optional[Nic]] = {f'  {rows[0]}': None, f'  {rows[1]}': None}

		for row, iface in zip(rows[2:], data):
			row = row.replace('|', '\\|')
			display_data[row] = iface

		return display_data

	def selected_action_display(self, nic: Nic) -> str:
		return nic.iface if nic.iface else ''

	def handle_action(self, action: str, entry: Optional[Nic], data: List[Nic]):
		if action == self._actions[0]:  # add
			iface = self._select_iface(data)
			if iface:
				nic = Nic(iface=iface)
				nic = self._edit_iface(nic)
				data += [nic]
		elif entry:
			if action == self._actions[1]:  # edit interface
				data = [d for d in data if d.iface != entry.iface]
				data.append(self._edit_iface(entry))
			elif action == self._actions[2]:  # delete
				data = [d for d in data if d != entry]

		return data

	def _select_iface(self, data: List[Nic]) -> Optional[str]:
		all_ifaces = list_interfaces().values()
		existing_ifaces = [d.iface for d in data]
		available = set(all_ifaces) - set(existing_ifaces)
		choice = Menu(str(_('Select interface to add')), list(available), skip=True).run()

		if choice.type_ == MenuSelectionType.Skip:
			return None

		return choice.single_value

	def _edit_iface(self, edit_nic: Nic) -> Nic:
		iface_name = edit_nic.iface
		modes = ['DHCP (auto detect)', 'IP (static)']
		default_mode = 'DHCP (auto detect)'

		prompt = _('Select which mode to configure for "{}" or skip to use default mode "{}"').format(iface_name, default_mode)
		mode = Menu(prompt, modes, default_option=default_mode, skip=False).run()

		if mode.value == 'IP (static)':
			while 1:
				prompt = _('Enter the IP and subnet for {} (example: 192.168.0.5/24): ').format(iface_name)
				ip = TextInput(prompt, edit_nic.ip).run().strip()
				# Implemented new check for correct IP/subnet input
				try:
					ipaddress.ip_interface(ip)
					break
				except ValueError:
					warn("You need to enter a valid IP in IP-config mode")

			# Implemented new check for correct gateway IP address
			gateway = None

			while 1:
				gateway = TextInput(
					_('Enter your gateway (router) IP address or leave blank for none: '),
					edit_nic.gateway
				).run().strip()
				try:
					if len(gateway) > 0:
						ipaddress.ip_address(gateway)
					break
				except ValueError:
					warn("You need to enter a valid gateway (router) IP address")

			if edit_nic.dns:
				display_dns = ' '.join(edit_nic.dns)
			else:
				display_dns = None
			dns_input = TextInput(_('Enter your DNS servers (space separated, blank for none): '), display_dns).run().strip()

			dns = []
			if len(dns_input):
				dns = dns_input.split(' ')

			return Nic(iface=iface_name, ip=ip, gateway=gateway, dns=dns, dhcp=False)
		else:
			# this will contain network iface names
			return Nic(iface=iface_name)


def ask_to_configure_network(preset: Optional[NetworkConfiguration]) -> Optional[NetworkConfiguration]:
	"""
		Configure the network on the newly installed system
	"""
	options = {n.display_msg(): n for n in NicType}
	preset_val = preset.type.display_msg() if preset else None
	warning = str(_('Are you sure you want to reset this setting?'))

	choice = Menu(
		_('Select one network interface to configure'),
		list(options.keys()),
		preset_values=preset_val,
		sort=False,
		allow_reset=True,
		allow_reset_warning_msg=warning
	).run()

	match choice.type_:
		case MenuSelectionType.Skip: return preset
		case MenuSelectionType.Reset: return None
		case MenuSelectionType.Selection:
			nic_type = options[choice.single_value]

			match nic_type:
				case NicType.ISO:
					return NetworkConfiguration(NicType.ISO)
				case NicType.NM:
					return NetworkConfiguration(NicType.NM)
				case NicType.MANUAL:
					preset_nics = preset.nics if preset else []
					nics = ManualNetworkConfig('Configure interfaces', preset_nics).run()
					if nics:
						return NetworkConfiguration(NicType.MANUAL, nics)

	return preset
