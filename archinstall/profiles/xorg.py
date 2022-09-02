import logging
from typing import Any, TYPE_CHECKING

from archinstall import log
from archinstall.lib.hardware import AVAILABLE_GFX_DRIVERS
from archinstall.profiles.profiles import Profile, ProfileType

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class XorgProfile(Profile):
	def __init__(
		self,
		name: str = 'Xorg',
		profile_type: ProfileType = ProfileType.Xorg,
		description: str = str(_('Installs a minimal system as well as xorg and graphics drivers.'))
	):
		super().__init__(
			name,
			profile_type,
			description=description,
			support_gfx_driver=True
		)

	def install(self, install_session: 'Installer'):
		try:
			driver_pkgs = AVAILABLE_GFX_DRIVERS[self.gfx_driver] if self.gfx_driver else []
			additional_pkg = ' '.join(['xorg-server', 'xorg-xinit'] + driver_pkgs)

			if self.gfx_driver is not None:
				if "nvidia" in self.gfx_driver:
					if "linux-zen" in install_session.base_packages or "linux-lts" in install_session.base_packages:
						for kernel in install_session.kernels:
							# Fixes https://github.com/archlinux/archinstall/issues/585
							install_session.add_additional_packages(f"{kernel}-headers")

						# I've had kernel regen fail if it wasn't installed before nvidia-dkms
						install_session.add_additional_packages("dkms xorg-server xorg-xinit nvidia-dkms")
						return
				elif 'amdgpu' in driver_pkgs:
					# The order of these two are important if amdgpu is installed #808
					if 'amdgpu' in install_session.MODULES:
						install_session.MODULES.remove('amdgpu')
					install_session.MODULES.append('amdgpu')

					if 'radeon' in install_session.MODULES:
						install_session.MODULES.remove('radeon')
					install_session.MODULES.append('radeon')

			install_session.add_additional_packages(additional_pkg)
		except Exception as err:
			log(f"Could not handle nvidia and linuz-zen specific situations during xorg installation: {err}", level=logging.WARNING, fg="yellow")
			# Prep didn't run, so there's no driver to install
			install_session.add_additional_packages("xorg-server xorg-xinit")
