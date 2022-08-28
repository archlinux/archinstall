import logging
from typing import Any, TYPE_CHECKING

from archinstall import log
from archinstall.lib.hardware import AVAILABLE_GFX_DRIVERS
from profiles_v2.profiles_v2 import ProfileV2, ProfileType

if TYPE_CHECKING:
	_: Any


class XorgProfileV2(ProfileV2):
	def __init__(
		self,
		name: str = 'Xorg',
		profile_type: ProfileType = ProfileType.Xorg,
		description: str = str(_('Installs a minimal system as well as xorg and graphics drivers.'))
	):
		super().__init__(
			name,
			profile_type,
			description=description
		)

	def with_graphic_driver(self) -> bool:
		return True

	def install(self, install_session: 'Installer'):
		try:
			driver_pkgs = AVAILABLE_GFX_DRIVERS[self.gfx_driver] if self.gfx_driver else []
			additional_pkg = ' '.join(['xorg-server', 'xorg-xinit'] + driver_pkgs)

			if "nvidia" in self.gfx_driver:
				if "linux-zen" in install_session.base_packages or "linux-lts" in install_session.base_packages:
					for kernel in install_session.kernels:
						# Fixes https://github.com/archlinux/archinstall/issues/585
						install_session.add_additional_packages(f"{kernel}-headers")

					# I've had kernel regen fail if it wasn't installed before nvidia-dkms
					install_session.add_additional_packages("dkms xorg-server xorg-xinit nvidia-dkms")
				else:
					install_session.add_additional_packages(additional_pkg)
			elif 'amdgpu' in driver_pkgs:
				# The order of these two are important if amdgpu is installed #808
				if 'amdgpu' in install_session.MODULES:
					install_session.MODULES.remove('amdgpu')
				install_session.MODULES.append('amdgpu')

				if 'radeon' in install_session.MODULES:
					install_session.MODULES.remove('radeon')
				install_session.MODULES.append('radeon')

				install_session.add_additional_packages(additional_pkg)
			else:
				install_session.add_additional_packages(additional_pkg)
		except Exception as err:
			log(f"Could not handle nvidia and linuz-zen specific situations during xorg installation: {err}", level=logging.WARNING, fg="yellow")
			# Prep didn't run, so there's no driver to install
			install_session.add_additional_packages("xorg-server xorg-xinit")
