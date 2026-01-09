from typing import override

from archinstall.default_profiles.profile import GreeterType, ProfileType
from archinstall.default_profiles.wayland import WaylandProfile


class NiriProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__(
			'Niri',
			ProfileType.WindowMgr,
		)

	@property
	@override
	def packages(self) -> list[str]:
		additional = []
		if seat := self.custom_settings.get('seat_access', None):
			additional = [seat]

		return [
			'niri',
			'alacritty',
			'fuzzel',
			'mako',
			'xorg-xwayland',
			'waybar',
			'swaybg',
			'swayidle',
			'swaylock',
			'xdg-desktop-portal-gnome',
		] + additional

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
