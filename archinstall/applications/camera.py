from typing import TYPE_CHECKING

from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class CameraApp:
	@property
	def packages(self) -> list[str]:
		return ['libcamera', 'libcamera-ipa', 'libcamera-tools', 'gst-plugin-libcamera', 'pipewire-libcamera']

	def install(self, install_session: 'Installer') -> None:
		debug('Installing libcamera')
		install_session.add_additional_packages(self.packages)
