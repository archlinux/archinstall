from __future__ import annotations

import ipaddress
from typing import assert_never, override

from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import EditMenu, SelectMenu
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType
from archinstall.tui.types import Alignment, FrameProperties

from ..menu.list_manager import ListManager
from ..models.network import NetworkConfiguration, Nic, NicType
from ..networking import list_interfaces


class ManualNetworkConfig(ListManager[Nic]):
	def __init__(self, prompt: str, preset: list[Nic]):
		self._actions = [
			tr('Add interface'),
			tr('Edit interface'),
			tr('Delete interface'),
		]

		super().__init__(
			preset,
			[self._actions[0]],
			self._actions[1:],
			prompt,
		)

	@override
	def selected_action_display(self, selection: Nic) -> str:
		return selection.iface if selection.iface else ''

	@override
	def handle_action(self, action: str, entry: Nic | None, data: list[Nic]) -> list[Nic]:
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

	def _select_iface(self, data: list[Nic]) -> str | None:
		all_ifaces = list_interfaces().values()
		existing_ifaces = [d.iface for d in data]
		available = set(all_ifaces) - set(existing_ifaces)

		if not available:
			return None

		if not available:
			return None

		items = [MenuItem(i, value=i) for i in available]
		group = MenuItemGroup(items, sort_items=True)

		result = SelectMenu[str](
			group,
			alignment=Alignment.CENTER,
			frame=FrameProperties.min(tr('Interfaces')),
			allow_skip=True,
		).run()

		match result.type_:
			case ResultType.Skip:
				return None
			case ResultType.Selection:
				return result.get_value()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')

	def _get_ip_address(
		self,
		title: str,
		header: str,
		allow_skip: bool,
		multi: bool,
		preset: str | None = None,
	) -> str | None:
		def validator(ip: str | None) -> str | None:
			failure = tr('You need to enter a valid IP in IP-config mode')

			if not ip:
				return failure

			if multi:
				ips = ip.split(' ')
			else:
				ips = [ip]

			try:
				for ip in ips:
					ipaddress.ip_interface(ip)
				return None
			except ValueError:
				return failure

		result = EditMenu(
			title,
			header=header,
			validator=validator,
			allow_skip=allow_skip,
			default_text=preset,
		).input()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				return result.text()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')

	def _edit_iface(self, edit_nic: Nic) -> Nic:
		iface_name = edit_nic.iface
		modes = ['DHCP (auto detect)', 'IP (static)']
		default_mode = 'DHCP (auto detect)'

		header = tr('Select which mode to configure for "{}"').format(iface_name) + '\n'
		items = [MenuItem(m, value=m) for m in modes]
		group = MenuItemGroup(items, sort_items=True)
		group.set_default_by_value(default_mode)

		result = SelectMenu[str](
			group,
			header=header,
			allow_skip=False,
			alignment=Alignment.CENTER,
			frame=FrameProperties.min(tr('Modes')),
		).run()

		match result.type_:
			case ResultType.Selection:
				mode = result.get_value()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')
			case ResultType.Skip:
				raise ValueError('The mode menu should not be skippable')
			case _:
				assert_never(result.type_)

		if mode == 'IP (static)':
			header = tr('Enter the IP and subnet for {} (example: 192.168.0.5/24): ').format(iface_name) + '\n'
			ip = self._get_ip_address(tr('IP address'), header, False, False)

			header = tr('Enter your gateway (router) IP address (leave blank for none)') + '\n'
			gateway = self._get_ip_address(tr('Gateway address'), header, True, False)

			if edit_nic.dns:
				display_dns = ' '.join(edit_nic.dns)
			else:
				display_dns = None

			header = tr('Enter your DNS servers with space separated (leave blank for none)') + '\n'
			dns_servers = self._get_ip_address(
				tr('DNS servers'),
				header,
				True,
				True,
				display_dns,
			)

			dns = []
			if dns_servers is not None:
				dns = dns_servers.split(' ')

			return Nic(iface=iface_name, ip=ip, gateway=gateway, dns=dns, dhcp=False)
		else:
			# this will contain network iface names
			return Nic(iface=iface_name)


def ask_to_configure_network(preset: NetworkConfiguration | None) -> NetworkConfiguration | None:
	"""
	Configure the network on the newly installed system
	"""

	items = [MenuItem(n.display_msg(), value=n) for n in NicType]
	group = MenuItemGroup(items, sort_items=True)

	if preset:
		group.set_selected_by_value(preset.type)

	result = SelectMenu[NicType](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Network configuration')),
		allow_reset=True,
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			config = result.get_value()

			match config:
				case NicType.ISO:
					return NetworkConfiguration(NicType.ISO)
				case NicType.NM:
					return NetworkConfiguration(NicType.NM)
				case NicType.MANUAL:
					preset_nics = preset.nics if preset else []
					nics = ManualNetworkConfig(tr('Configure interfaces'), preset_nics).run()

					if nics:
						return NetworkConfiguration(NicType.MANUAL, nics)

	return preset
