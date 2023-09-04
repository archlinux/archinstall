from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType
from archinstall.default_profiles.xorg import XorgProfile

if TYPE_CHECKING:
	_: Any


class BspwmProfile(XorgProfile):
	def __init__(self):
		super().__init__('Bspwm', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		# return super().packages + [
		return [
			'bspwm',
			'sxhkd',
			'dmenu',
			'xdo',
			'rxvt-unicode'
		]

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Lightdm

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()

		# The wiki specified xinit, but we already use greeter?
		# https://wiki.archlinux.org/title/Bspwm#Starting
		#
		# # TODO: check if we selected a greeter, else run this:
		# with open(f"{install_session.target}/etc/X11/xinit/xinitrc", 'r') as xinitrc:
		# 	xinitrc_data = xinitrc.read()

		# for line in xinitrc_data.split('\n'):
		# 	if "twm &" in line:
		# 		xinitrc_data = xinitrc_data.replace(line, f"# {line}")
		# 	if "xclock" in line:
		# 		xinitrc_data = xinitrc_data.replace(line, f"# {line}")
		# 	if "xterm" in line:
		# 		xinitrc_data = xinitrc_data.replace(line, f"# {line}")

		# xinitrc_data += '\n'
		# xinitrc_data += 'exec bspwn\n'

		# with open(f"{install_session.target}/etc/X11/xinit/xinitrc", 'w') as xinitrc:
		# 	xinitrc.write(xinitrc_data)
