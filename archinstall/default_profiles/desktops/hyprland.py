from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType, SelectResult
from archinstall.default_profiles.xorg import XorgProfile
from archinstall.lib.menu.menu import Menu

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any


class HyprlandProfile(XorgProfile):
	def __init__(self):
		super().__init__('Hyprland', ProfileType.WindowMgr, description='')

	@property
	def packages(self) -> List[str]:
		return [
			"hyprland",
			"dunst",
			"xdg-desktop-portal-hyprland",
			"kitty",
			"qt5-wayland",
			"qt6-wayland"
			"waybar-hyprland",
			"grim",
			"slurp",
			"hyprpaper",
		]
  

	def post_install(self, install_session: 'Installer'):
		# Fix seatd
		install_session.arch_chroot("systemctl enable seatd")
		# For nvidia:
			# install_session.arch_chroot("pacman -Sy nvidia-dkms")
			# if install_session.bootloader == "systemd-boot":
			# 	install_session.arch_chroot("echo nvidia_drm.modeset=1 >> /boot/loader/entries/arch.conf")
			# elif install_session.bootloader == "GRUB":
			# 	with open(f"{install_session.target}/etc/default/grub", "r") as f:
			# 		c = f.readlines()
			# 	for i,line in enumerate(c):
			# 		if line.startswith("GRUB_CMDLINE_LINUX_DEFAULT="):
			# 			c[i] = f"{c[i:-1]} nvidia_drm.modeset=1\""
			# 	with open(f"{install_session.target}/etc/default/grub", "w") as f:
			# 		f.write(c)
			# 	install_session.arch_chroot("grub-mkconfig -o /boot/grub/grub.cfg")
			# 	install_session.modules += ["nvidia", "nvidia_modeset", "nvidia_uvm", "nvidia_drm"]
			# install_session.arch_chroot("echo options nvidia-drm modeset=1 >> /etc/modprobe.d/nvidia.conf")
			# if self.multi-monitor: # Check with lshw -c display
			# 	install_session.arch_chroot("pacman -R optimus-manager")
			# 	warn_user("You need to change your BIOS settings from hybrid graphics to discrete graphics")
			# for user in self.selected_users:
			# 	with open(f"{install_session.target}/home/{user}/.config/hypr/hyprland.conf", "a") as f:
			# 		f.writelines([
			# 			"env = LIBVA_DRIVER_NAME,nvidia",
			# 			"env = XDG_SESSION_TYPE,wayland",
			# 			"env = GBM_BACKEND,nvidia-drm",
			# 			"env = __GLX_VENDOR_LIBRARY_NAME,nvidia",
			# 			"env = WLR_NO_HARDWARE_CURSORS,1"
			# 		])
   
	# def do_on_select(self):
	# 	title = str(_("Configure Hyprland"))
	# 	options = []
	# 	options += str(_(f"Select users ({' '.join(self.selected_users)})"))
	# 	#TODO: Configure seat access (seatd / polkit)
	# 	chosen = Menu(title, options, skip=False).run()
	# 	if chosen.value.startswith("Select users"):
	# 		user_selected = Menu("Select User(s)", created_users, multi=True).run()
	# 		self.selected_users = user_selected.multi_value
  

	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Sddm

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
