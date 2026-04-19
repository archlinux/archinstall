from typing import TYPE_CHECKING

from archinstall.lib.models.application import AURHelper, AURHelperConfiguration
from archinstall.lib.models.users import User
from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class AURHelperApp:
	@property
	def yay_packages(self) -> list[str]:
		return [
			'base-devel',
			'git',
			'go',  # required to build yay
		]

	@property
	def paru_packages(self) -> list[str]:
		return [
			'base-devel',
			'git',
			'rust',  # required to build paru
		]

	def _write_firstboot_service(
		self,
		install_session: Installer,
		helper: str,
		user: User,
	) -> None:
		"""
		Writes a systemd oneshot service that builds and installs the AUR helper
		on first boot as the real user, then removes itself.
		makepkg cannot run as root and needs a real user session to work
		correctly, so we defer it to first boot instead of running it during
		the archinstall chroot environment.

		The service runs as root so it can write/remove the temporary sudoers
		rule, and explicitly su's to the user only for the makepkg step.
		"""
		repo_url = f'https://aur.archlinux.org/{helper}.git'
		build_dir = f'/home/{user.username}/{helper}-build'
		service_name = f'aur-install-{helper}'
		sudoers_rule = f'/etc/sudoers.d/99-aur-{helper}-tmp'

		service_content = f"""\
[Unit]
Description=Install {helper} AUR helper (first boot)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
# Run as root so we can write/remove the sudoers rule
ExecStartPre=/bin/bash -c 'echo "{user.username} ALL=(ALL) NOPASSWD: /usr/bin/pacman" > {sudoers_rule} && chmod 440 {sudoers_rule}'
# makepkg is invoked via su to the actual user.
ExecStart=/bin/su - {user.username} -c 'git clone {repo_url} {build_dir} && cd {build_dir} && makepkg -si --noconfirm && rm -rf {build_dir}'
ExecStartPost=/bin/rm -f {sudoers_rule}
ExecStartPost=/bin/rm -f /etc/systemd/system/{service_name}.service
ExecStartPost=/bin/systemctl daemon-reload
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
		service_path = install_session.target / 'etc' / 'systemd' / 'system' / f'{service_name}.service'
		service_path.write_text(service_content)

		install_session.enable_service([f'{service_name}.service'])

		debug(f'First-boot service written for {helper}, will install as {user.username}')

	def install(
		self,
		install_session: Installer,
		AUR_config: AURHelperConfiguration,
		users: list[User] | None = None,
	) -> None:
		debug(f'Installing AUR helper: {AUR_config.AUR_helper.value}')

		if AUR_config.AUR_helper == AURHelper.NO_AUR_HELPER:
			debug('No AUR helper selected, skipping installation.')
			return

		if not users:
			debug('No users provided, skipping AUR helper installation.')
			return

		user = users[0]

		match AUR_config.AUR_helper:
			case AURHelper.YAY:
				install_session.add_additional_packages(self.yay_packages)
				self._write_firstboot_service(install_session, 'yay', user)
			case AURHelper.PARU:
				install_session.add_additional_packages(self.paru_packages)
				self._write_firstboot_service(install_session, 'paru', user)