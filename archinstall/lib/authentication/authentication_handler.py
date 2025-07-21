import getpass
from pathlib import Path
from typing import TYPE_CHECKING

from archinstall.lib.general import SysCommandWorker
from archinstall.lib.models.authentication import AuthenticationConfiguration, U2FLoginConfiguration, U2FLoginMethod
from archinstall.lib.models.users import User
from archinstall.lib.output import debug
from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import Tui

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class AuthenticationHandler:
	def setup_auth(
		self,
		install_session: 'Installer',
		auth_config: AuthenticationConfiguration,
		hostname: str,
	) -> None:
		if auth_config.u2f_config and auth_config.users is not None:
			self._setup_u2f_login(install_session, auth_config.u2f_config, auth_config.users, hostname)

	def _setup_u2f_login(self, install_session: 'Installer', u2f_config: U2FLoginConfiguration, users: list[User], hostname: str) -> None:
		self._configure_u2f_mapping(install_session, u2f_config, users, hostname)
		self._update_pam_config(install_session, u2f_config)

	def _update_pam_config(
		self,
		install_session: 'Installer',
		u2f_config: U2FLoginConfiguration,
	) -> None:
		match u2f_config.u2f_login_method:
			case U2FLoginMethod.Passwordless:
				config_entry = 'auth sufficient pam_u2f.so authfile=/etc/u2f_mappings cue'
			case U2FLoginMethod.SecondFactor:
				config_entry = 'auth required pam_u2f.so authfile=/etc/u2f_mappings cue'
			case _:
				raise ValueError(f'Unknown U2F login method: {u2f_config.u2f_login_method}')

		debug(f'U2F PAM configuration: {config_entry}')
		debug(f'Passwordless sudo enabled: {u2f_config.passwordless_sudo}')

		sudo_config = install_session.target / 'etc/pam.d/sudo'
		sys_login = install_session.target / 'etc/pam.d/system-login'

		if u2f_config.passwordless_sudo:
			self._add_u2f_entry(sudo_config, config_entry)

		self._add_u2f_entry(sys_login, config_entry)

	def _add_u2f_entry(self, file: Path, entry: str) -> None:
		if not file.exists():
			debug(f'File does not exist: {file}')
			return None

		content = file.read_text().splitlines()

		# remove any existing u2f auth entry
		content = [line for line in content if 'pam_u2f.so' not in line]

		# add the u2f auth entry as the first one after comments
		for i, line in enumerate(content):
			if not line.startswith('#'):
				content.insert(i, entry)
				break
		else:
			content.append(entry)

		file.write_text('\n'.join(content) + '\n')

	def _configure_u2f_mapping(
		self,
		install_session: 'Installer',
		u2f_config: U2FLoginConfiguration,
		users: list[User],
		hostname: str,
	) -> None:
		debug(f'Setting up U2F login: {u2f_config.u2f_login_method.value}')

		install_session.pacman.strap('pam-u2f')

		Tui.print(tr(f'Setting up U2F login: {u2f_config.u2f_login_method.value}'))

		# https://developers.yubico.com/pam-u2f/
		u2f_auth_file = install_session.target / 'etc/u2f_mappings'
		u2f_auth_file.touch()
		existing_keys = u2f_auth_file.read_text()

		registered_keys: list[str] = []

		for user in users:
			Tui.print('')
			Tui.print(tr('Setting up U2F device for user: {}').format(user.username))
			Tui.print(tr('You may need to enter the PIN and then touch your U2F device to register it'))

			cmd = ' '.join(['arch-chroot', str(install_session.target), 'pamu2fcfg', '-u', user.username, '-o', f'pam://{hostname}', '-i', f'pam://{hostname}'])

			debug(f'Enrolling U2F device: {cmd}')

			worker = SysCommandWorker(cmd, peek_output=True)
			pin_inputted = False

			while worker.is_alive():
				if pin_inputted is False:
					if bytes('enter pin for', 'UTF-8') in worker._trace_log.lower():
						worker.write(bytes(getpass.getpass(''), 'UTF-8'))
						pin_inputted = True

			output = worker.decode().strip().splitlines()
			debug(f'Output from pamu2fcfg: {output}')

			key = output[-1].strip()
			registered_keys.append(key)

		all_keys = '\n'.join(registered_keys)

		if existing_keys:
			existing_keys += f'\n{all_keys}'
		else:
			existing_keys = all_keys

		u2f_auth_file.write_text(existing_keys)


auth_handler = AuthenticationHandler()
