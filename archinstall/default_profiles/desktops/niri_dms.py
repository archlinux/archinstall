import shutil
from pathlib import Path
from typing import TYPE_CHECKING, override

from archinstall.default_profiles.profile import DisplayServerType, GreeterType, Profile, ProfileType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	from archinstall.lib.models.users import User


_TERMINAL = 'alacritty'
_ASSETS_DIR = Path(__file__).parent / 'niri_dms_assets'


class NiriDmsProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'niri - DankMaterialShell',
			ProfileType.WindowMgr,
			support_gfx_driver=True,
			display_server=DisplayServerType.Wayland,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'niri',
			'dms-shell-niri',
			'polkit',
			'xdg-desktop-portal-gnome',
			'xorg-xwayland',
			'matugen',
			'cava',
			'kimageformats',
			'cups-pk-helper',
			'tuned-ppd',
			_TERMINAL,
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.GreetdDms

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		binds = (_ASSETS_DIR / 'dms/binds.kdl').read_text().replace('{{TERMINAL_COMMAND}}', _TERMINAL)

		for user in users:
			home = install_session.target / 'home' / user.username
			niri_dir = home / '.config/niri'
			dms_dir = niri_dir / 'dms'
			dms_dir.mkdir(parents=True, exist_ok=True)

			shutil.copy(_ASSETS_DIR / 'niri.kdl', niri_dir / 'config.kdl')
			for name in ('colors.kdl', 'layout.kdl', 'alttab.kdl', 'outputs.kdl', 'cursor.kdl'):
				shutil.copy(_ASSETS_DIR / 'dms' / name, dms_dir / name)
			(dms_dir / 'binds.kdl').write_text(binds)

			niri_unit_dropin = home / '.config/systemd/user/niri.service.d'
			niri_unit_dropin.mkdir(parents=True, exist_ok=True)
			(niri_unit_dropin / 'dms.conf').write_text('[Unit]\nWants=dms.service\n')

			install_session.arch_chroot(f'chown -R {user.username}:{user.username} /home/{user.username}/.config')
