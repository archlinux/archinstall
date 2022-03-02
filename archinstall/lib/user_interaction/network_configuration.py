from __future__ import annotations

import ipaddress
import logging
from copy import copy
from typing import Any, Optional, Dict, TYPE_CHECKING

from ..menu.text_input import TextInput
from ..models.network_configuration import NetworkConfiguration, NicType

from ..networking import list_interfaces
from ..menu import Menu
from ..output import log

if TYPE_CHECKING:
  _: Any


def ask_to_configure_network(preset :Dict[str, Any] = {}) -> Optional[NetworkConfiguration]:
	"""
		Configure the network on the newly installed system
	"""
	interfaces = {
		'none': str(_('No network configuration')),
		'iso_config': str(_('Copy ISO network configuration to installation')),
		'network_manager': str(_('Use NetworkManager (necessary to configure internet graphically in GNOME and KDE)')),
		**list_interfaces()
	}
	# for this routine it's easier to set the cursor position rather than a preset value
	cursor_idx = None
	if preset:
		if preset['type'] == 'iso_config':
			cursor_idx = 0
		elif preset['type'] == 'network_manager':
			cursor_idx = 1
		else:
			try :
				# let's hope order in dictionaries stay
				cursor_idx = list(interfaces.values()).index(preset.get('type'))
			except ValueError:
				pass

	nic = Menu(_('Select one network interface to configure'), interfaces.values(), cursor_index=cursor_idx, sort=False).run()

	if not nic:
		return None

	if nic == interfaces['none']:
		return None
	elif nic == interfaces['iso_config']:
		return NetworkConfiguration(NicType.ISO)
	elif nic == interfaces['network_manager']:
		return NetworkConfiguration(NicType.NM)
	else:
		# Current workaround:
		# For selecting modes without entering text within brackets,
		# printing out this part separate from options, passed in
		# `generic_select`
		# we only keep data if it is the same nic as before
		if preset.get('type') != nic:
			preset_d = {'type': nic, 'dhcp': True, 'ip': None, 'gateway': None, 'dns': []}
		else:
			preset_d = copy(preset)

		modes = ['DHCP (auto detect)', 'IP (static)']
		default_mode = 'DHCP (auto detect)'
		cursor_idx = 0 if preset_d.get('dhcp',True) else 1

		prompt = _('Select which mode to configure for "{}" or skip to use default mode "{}"').format(nic, default_mode)
		mode = Menu(prompt, modes, default_option=default_mode, cursor_index=cursor_idx).run()
		# TODO preset values for ip and gateway
		if mode == 'IP (static)':
			while 1:
				prompt = _('Enter the IP and subnet for {} (example: 192.168.0.5/24): ').format(nic)
				ip = TextInput(prompt,preset_d.get('ip')).run().strip()
				# Implemented new check for correct IP/subnet input
				try:
					ipaddress.ip_interface(ip)
					break
				except ValueError:
					log(
						"You need to enter a valid IP in IP-config mode.",
						level=logging.WARNING,
						fg='red'
					)

			# Implemented new check for correct gateway IP address
			while 1:
				gateway = TextInput(_('Enter your gateway (router) IP address or leave blank for none: '),preset_d.get('gateway')).run().strip()
				try:
					if len(gateway) == 0:
						gateway = None
					else:
						ipaddress.ip_address(gateway)
					break
				except ValueError:
					log(
						"You need to enter a valid gateway (router) IP address.",
						level=logging.WARNING,
						fg='red'
					)

			dns = None
			if preset_d.get('dns'):
				preset_d['dns'] = ' '.join(preset_d['dns'])
			else:
				preset_d['dns'] = None
			dns_input = TextInput(_('Enter your DNS servers (space separated, blank for none): '),preset_d['dns']).run().strip()

			if len(dns_input):
				dns = dns_input.split(' ')

			return NetworkConfiguration(
				NicType.MANUAL,
				iface=nic,
				ip=ip,
				gateway=gateway,
				dns=dns,
				dhcp=False
			)
		else:
			# this will contain network iface names
			return NetworkConfiguration(NicType.MANUAL, iface=nic)
