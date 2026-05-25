from typing import TYPE_CHECKING

from archinstall.lib.log import debug
from archinstall.lib.models.plymouth import PlymouthConfiguration, PlymouthTheme

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class PlymouthHandler:
	@property
	def plymouth_packages(self) -> list[str]:
		return [
			'plymouth',
		]

	@property
	def kernel_params(self) -> list[str]:
		return [
			'quiet',
			'splash',
		]

	@property
	def plymouth_hook(self) -> str:
		return 'plymouth'

	@property
	def _hook_anchors(self) -> list[tuple[str, bool]]:
		return [
			# hook_name, insert_after
			('encrypt', False),
			('sd-encrypt', False),
			('systemd', True),
			('systemd', True),
			('filesystems', False),
			('keyboard', True),
		]

	def install(self, install_session: Installer, plymouth_config: PlymouthConfiguration) -> None:
		debug(f'Installing plymouth with theme: {plymouth_config.plymouth.value}')

		if plymouth_config.plymouth == PlymouthTheme.DISABLED:
			debug('No plymouth theme selected, skipping installation.')
			return

		install_session.add_additional_packages(self.plymouth_packages)

		self._add_kernel_params(install_session)
		self._add_hooks(install_session)
		self._set_theme(install_session, plymouth_config.plymouth.value)
		self._regenerate_mkinitcpio(install_session)

		debug('Plymouth install completed')

	def _add_kernel_params(self, install_session: Installer) -> None:
		debug(f'Adding kernel params for plymouth {self.kernel_params}')
		for param in self.kernel_params:
			if param not in install_session._kernel_params:
				install_session._kernel_params.append(param)

	def _add_hooks(self, install_session: Installer) -> None:
		debug('Adding Plymouth hook')

		if self.plymouth_hook in install_session._hooks:
			debug(f'{self.plymouth_hook} hook already present')
			return

		for hook, insert_after in self._hook_anchors:
			try:
				index = install_session._hooks.index(hook)
				position = index + (1 if insert_after else 0)
				install_session._hooks.insert(position, self.plymouth_hook)
				debug(f'Plymouth hook inserted {["before", "after"][insert_after]} {hook!r}')
				return
			except ValueError:
				continue

		install_session._hooks.append(self.plymouth_hook)
		debug('Plymouth hook appended at end (no anchor hook found)')

	def _set_theme(self, install_session: Installer, theme: str) -> None:
		debug(f'Set plymouth theme to {theme}')
		install_session.arch_chroot(f'plymouth-set-default-theme {theme}')

	def _regenerate_mkinitcpio(self, install_session: Installer) -> None:
		install_session.mkinitcpio(['-P'])
