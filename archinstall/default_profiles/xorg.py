from typing import TYPE_CHECKING, override

from archinstall.default_profiles.profile import Profile, ProfileType

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class XorgProfile(Profile):
	def __init__(
		self,
		name: str = "Xorg",
		profile_type: ProfileType = ProfileType.Xorg,
		advanced: bool = False,
	):
		super().__init__(
			name,
			profile_type,
			support_gfx_driver=True,
			advanced=advanced,
		)

	@override
	def preview_text(self) -> str:
		text = str(_("Environment type: {}")).format(self.profile_type.value)
		if packages := self.packages_text():
			text += f"\n{packages}"

		return text

	@property
	@override
	def packages(self) -> list[str]:
		return [
			"xorg-server",
		]
