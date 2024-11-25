from typing import TYPE_CHECKING

from archinstall.default_profiles.profile import Profile, ProfileType

if TYPE_CHECKING:
	from collections.abc import Callable

	from archinstall.lib.translationhandler import DeferredTranslation

	_: Callable[[str], DeferredTranslation]


class MinimalProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Minimal',
			ProfileType.Minimal,
			description=str(_('A very basic installation that allows you to customize Arch Linux as you see fit.'))
		)
