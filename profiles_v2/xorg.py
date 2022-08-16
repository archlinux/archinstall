from typing import List, Any, TYPE_CHECKING

from archinstall import select_driver

from profiles_v2.profiles_v2 import ProfileV2, ProfileType, SelectResult
from archinstall.lib.hardware import __packages__ as __hwd__packages__

if TYPE_CHECKING:
	_: Any


class XorgProfileV2(ProfileV2):
	def __init__(
		self,
		name: str = 'Xorg',
		profile_type: ProfileType = ProfileType.Generic,
		description: str = str(_('Installs a minimal system as well as xorg and graphics drivers.'))
	):
		super().__init__(
			name,
			profile_type,
			description=description
		)

	def packages(self) -> List[str]:
		return [
			'dkms',
			'xorg-server',
			'xorg-xinit',
			'nvidia-dkms',
			*__hwd__packages__
		]

	def do_on_select(self) -> SelectResult:
		self.gfx_driver = select_driver(current_value=self.gfx_driver)
		return SelectResult.NewSelection


# Ensures that this code only gets executed if executed
# through importlib.util.spec_from_file_location("xorg", "/somewhere/xorg.py")
# or through conventional import xorg
# if __name__ == 'xorg':
# 	try:
# 		if "nvidia" in archinstall.storage.get("gfx_driver_packages", []):
# 			if "linux-zen" in archinstall.storage['installation_session'].base_packages or "linux-lts" in archinstall.storage['installation_session'].base_packages:
# 				for kernel in archinstall.storage['installation_session'].kernels:
# 					archinstall.storage['installation_session'].add_additional_packages(f"{kernel}-headers") # Fixes https://github.com/archlinux/archinstall/issues/585
# 				archinstall.storage['installation_session'].add_additional_packages("dkms")  # I've had kernel regen fail if it wasn't installed before nvidia-dkms
# 				archinstall.storage['installation_session'].add_additional_packages("xorg-server xorg-xinit nvidia-dkms")
# 			else:
# 				archinstall.storage['installation_session'].add_additional_packages(f"xorg-server xorg-xinit {' '.join(archinstall.storage.get('gfx_driver_packages', []))}")
# 		elif 'amdgpu' in archinstall.storage.get("gfx_driver_packages", []):
# 			# The order of these two are important if amdgpu is installed #808
# 			if 'amdgpu' in archinstall.storage['installation_session'].MODULES:
# 				archinstall.storage['installation_session'].MODULES.remove('amdgpu')
# 			archinstall.storage['installation_session'].MODULES.append('amdgpu')
#
# 			if 'radeon' in archinstall.storage['installation_session'].MODULES:
# 				archinstall.storage['installation_session'].MODULES.remove('radeon')
# 			archinstall.storage['installation_session'].MODULES.append('radeon')
#
# 			archinstall.storage['installation_session'].add_additional_packages(f"xorg-server xorg-xinit {' '.join(archinstall.storage.get('gfx_driver_packages', []))}")
# 		else:
# 			archinstall.storage['installation_session'].add_additional_packages(f"xorg-server xorg-xinit {' '.join(archinstall.storage.get('gfx_driver_packages', []))}")
# 	except Exception as err:
# 		archinstall.log(f"Could not handle nvidia and linuz-zen specific situations during xorg installation: {err}", level=logging.WARNING, fg="yellow")
# 		archinstall.storage['installation_session'].add_additional_packages("xorg-server xorg-xinit")  # Prep didn't run, so there's no driver to install
