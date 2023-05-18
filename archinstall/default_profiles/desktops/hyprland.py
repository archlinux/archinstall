from enum import Enum
from typing import List, Optional, Any, TYPE_CHECKING

from archinstall.default_profiles.profile import ProfileType, GreeterType, SelectResult
from archinstall.default_profiles.xorg import XorgProfile
from archinstall.lib.menu.menu import Menu

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer
	_: Any

class FileManager(Enum):
    dolphin = 'dolphin'
    thunar = 'thunar'

HYPRLAND_CONFIG = """# THIS IS PRECONFIGURED BY ARCHINSTALL
# The wiki for hyprland is here : https://wiki.hyprland.org/Getting-Started/Master-Tutorial
# If you encounter any problems, bugs or crashes, go and check the wiki
# Have fun !

monitor=,preferred,auto,auto

exec-once = waybar & hyprpaper & kitty # Autostarting kitty if you have problems with keyboard shortcuts etc.")

env = XCURSOR_SIZE,24

input {
    kb_layout = {kb}
    kb_variant =
    kb_model =
    kb_options =
    kb_rules =
    follow_mouse = 1
    touchpad { natural_scroll = false }
    sensitivity = 0 # -1.0 - 1.0, 0 means no modification.
}
            
general {
    # See https://wiki.hyprland.org/Configuring/Variables/ for more
    gaps_in = 5
    gaps_out = 20
    border_size = 2
    col.active_border = rgba(33ccffee) rgba(00ff99ee) 45deg
    col.inactive_border = rgba(595959aa)

    layout = dwindle
}

decoration {
    # See https://wiki.hyprland.org/Configuring/Variables/ for more
    rounding = 10
    blur = true
    blur_size = 3
    blur_passes = 1
    blur_new_optimizations = true

    drop_shadow = true
    shadow_range = 4
    shadow_render_power = 3
    col.shadow = rgba(1a1a1aee)
}

animations {
    enabled = true
    # Some default animations, see https://wiki.hyprland.org/Configuring/Animations/ for more
    bezier = myBezier, 0.05, 0.9, 0.1, 1.05

    animation = windows, 1, 7, myBezier
    animation = windowsOut, 1, 7, default, popin 80%
    animation = border, 1, 10, default
    animation = borderangle, 1, 8, default
    animation = fade, 1, 7, default
    animation = workspaces, 1, 6, default
}

dwindle {
    # See https://wiki.hyprland.org/Configuring/Dwindle-Layout/ for more
    pseudotile = true # master switch for pseudotiling. Enabling is bound to mainMod + P in the keybinds section below
    preserve_split = true # you probably want this
}

master {
    # See https://wiki.hyprland.org/Configuring/Master-Layout/ for more
    new_is_master = true
}

gestures {
    # See https://wiki.hyprland.org/Configuring/Variables/ for more
    workspace_swipe = false
}
$mainMod = SUPER

bind = $mainMod, Q, exec, kitty
bind = $mainMod, C, killactive,
bind = $mainMod, M, exit,
bind = $mainMod, E, exec, {fm}
bind = $mainMod, V, togglefloating,
bind = $mainMod, R, exec, wofi --show drun
bind = $mainMod, P, pseudo, # dwindle
bind = $mainMod, J, togglesplit, # dwindle

# Move focus with mainMod + arrow keys
bind = $mainMod, left, movefocus, l
bind = $mainMod, right, movefocus, r
bind = $mainMod, up, movefocus, u
bind = $mainMod, down, movefocus, d

# Switch workspaces with mainMod + [0-9]
bind = $mainMod, 1, workspace, 1
bind = $mainMod, 2, workspace, 2
bind = $mainMod, 3, workspace, 3
bind = $mainMod, 4, workspace, 4
bind = $mainMod, 5, workspace, 5
bind = $mainMod, 6, workspace, 6
bind = $mainMod, 7, workspace, 7
bind = $mainMod, 8, workspace, 8
bind = $mainMod, 9, workspace, 9
bind = $mainMod, 0, workspace, 10

# Move active window to a workspace with mainMod + SHIFT + [0-9]
bind = $mainMod SHIFT, 1, movetoworkspace, 1
bind = $mainMod SHIFT, 2, movetoworkspace, 2
bind = $mainMod SHIFT, 3, movetoworkspace, 3
bind = $mainMod SHIFT, 4, movetoworkspace, 4
bind = $mainMod SHIFT, 5, movetoworkspace, 5
bind = $mainMod SHIFT, 6, movetoworkspace, 6
bind = $mainMod SHIFT, 7, movetoworkspace, 7
bind = $mainMod SHIFT, 8, movetoworkspace, 8
bind = $mainMod SHIFT, 9, movetoworkspace, 9
bind = $mainMod SHIFT, 0, movetoworkspace, 10

# Scroll through existing workspaces with mainMod + scroll
bind = $mainMod, mouse_down, workspace, e+1
bind = $mainMod, mouse_up, workspace, e-1

# Move/resize windows with mainMod + LMB/RMB and dragging
bindm = $mainMod, mouse:272, movewindow
bindm = $mainMod, mouse:273, resizewindow
"""

HYPRPAPER_CONFIG = """# PRECONFIGURED BY ARCHINSTALL
# Before changing wallpaper, check how stuff works : https://github.com/hyprwm/hyprpaper#Usage
preload = {path}
wallpaper = ,{path}"""

WAYBAR_CONFIG = """"""
WAYBAR_CSS = """# PRECONFIGURED BY ARCHINSTALL
# Configure as you need, and check some examples on the internet
* {
	font-size: 12px;
	font-family: monospace;
	font-weight: bold;
}

window#waybar {
	background: #292b2e;
	color: #fdf6e3;
}"""

WLOGOUT_CONFIG = """# PRECONFIGURED BY ARCHINSTALL
# INSPIRED BY SOLDOESTECH : https://github.com/SolDoesTech/HyprV2/blob/main/wlogout/layout
{
    "label" : "lock",
    "action" : "swaylock",
    "text" : "Lock"
}

{
    "label" : "hibernate",
    "action" : "systemctl hibernate",
    "text" : "Hibernate"
}

{
    "label" : "logout",
    "action" : "hyprctl dispatch exit 0",
    "text" : "Logout"
}

{
    "label" : "shutdown",
    "action" : "systemctl poweroff",
    "text" : "Shutdown"
}

{
    "label" : "suspend",
    "action" : "systemctl suspend",
    "text" : "Suspend"
}

{
    "label" : "reboot",
    "action" : "systemctl reboot",
    "text" : "Reboot"
}
"""

def get_hypr_conf(keyboard_layout, file_manager):
    return HYPRLAND_CONFIG.format(kb=keyboard_layout, fm=file_manager)
def get_wallpaper_conf(wallpaper_path):
    return HYPRPAPER_CONFIG.format(path=wallpaper_path)
def get_waybar_conf():
    return WAYBAR_CONFIG
def get_waybar_css():
    return WAYBAR_CSS
def get_wlogout_config():
    return WLOGOUT_CONFIG

def write_config(path, content):
	with open(path, "w") as f:
		f.write(content)

class HyprlandProfile(XorgProfile):
	def __init__(self):
		super().__init__('Hyprland', ProfileType.WindowMgr, description='')
		self.selected_users = []
		self.file_manager = FileManager.dolphin

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
			"wlogout",
			"swaylock"
		]
  

	def post_install(self, install_session: 'Installer'):
		# Fix seatd
		install_session.arch_chroot("systemctl enable seatd")
		keyboard_layout = "us" #TODO: How to get selected keyboard layout for user ?
		dirs = "hypr/wallpapers", "waybar", "wlogout"
		for user in self.selected_users:
			chrooted_conf = f"/home/{user}/.config"
			for dir in dirs:
				install_session.arch_chroot(f"mkdir {chrooted_conf}/{dir} -p")
			install_session.arch_chroot(f"wget --output {chrooted_conf}/hypr/wallpapers/default_arch.jpg https://images.hdqwalls.com/wallpapers/arch-liinux-4k-t0.jpg")
			uconf = f"{install_session.target}{chrooted_conf}"

			write_config(f"{uconf}/hypr/hyprland.conf",  get_hypr_conf(keyboard_layout, self.file_manager.value))
			write_config(f"{uconf}/hypr/hyprpaper.conf", get_wallpaper_conf(f"{uconf}/hypr/wallpapers/default_arch.jpg"))
			write_config(f"{uconf}/waybar/config",       get_waybar_conf())
			write_config(f"{uconf}/waybar/style.css",    get_waybar_css())
			write_config(f"{uconf}/wlogout/layout",      get_wlogout_config())

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
   
	def do_on_select(self):
		title = str(_("Configure Hyprland"))
		options = []
		options += str(_(f"Select users ({' '.join(self.selected_users)})"))
		options += str(_(f"File manager ({self.file_manager})"))
		
		#TODO: Configure seat access (seatd / polkit)
  
		chosen = Menu(title, options, skip=False).run()
		if chosen.value.startswith("Select users"):
			already_created_users = []
			user_selected = Menu("Select User(s)", already_created_users, multi=True, preset_values=self.selected_users).run()
			self.selected_users = user_selected.multi_value
		elif chosen.value.startswith("File manager"):
			self.file_manager = Menu("Select graphical file manager", [fm.value for fm in FileManager]).run().value



	@property
	def default_greeter_type(self) -> Optional[GreeterType]:
		return GreeterType.Sddm

	def preview_text(self) -> Optional[str]:
		text = str(_('Environment type: {}')).format(self.profile_type.value)
		return text + '\n' + self.packages_text()
