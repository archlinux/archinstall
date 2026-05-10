from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, TypedDict, override

from archinstall.default_profiles.profile import GreeterType, Profile
from archinstall.lib.hardware import GfxDriver
from archinstall.lib.models.config import SubConfig
from archinstall.lib.translationhandler import tr

if TYPE_CHECKING:
	from archinstall.lib.profile.profiles_handler import ProfileSerialization


class _ProfileConfigurationSerialization(TypedDict):
	profile: ProfileSerialization
	gfx_driver: str | None
	greeter: str | None


@dataclass
class ProfileConfiguration(SubConfig):
	profile: Profile | None = None
	gfx_driver: GfxDriver | None = None
	greeter: GreeterType | None = None

	@override
	def json(self) -> _ProfileConfigurationSerialization:
		from archinstall.lib.profile.profiles_handler import profile_handler

		return {
			'profile': profile_handler.to_json(self.profile),
			'gfx_driver': self.gfx_driver.value if self.gfx_driver else None,
			'greeter': self.greeter.value if self.greeter else None,
		}

	@override
	def summary(self) -> list[str] | None:
		out: list[str] = []

		if self.profile:
			out.append(self.profile.name)

			if self.gfx_driver:
				out.append(tr('{} grphics driver').format(self.gfx_driver.value))

			if self.greeter:
				out.append(tr('{} greeter').format(self.greeter.value))

			return out

		return None

	@classmethod
	def parse_arg(cls, arg: _ProfileConfigurationSerialization) -> Self:
		from archinstall.lib.profile.profiles_handler import profile_handler

		profile = profile_handler.parse_profile_config(arg['profile'])
		greeter = arg.get('greeter', None)
		gfx_driver = arg.get('gfx_driver', None)

		if gfx_driver == 'Nvidia (proprietary)':
			raise ValueError(
				'The Nvidia proprietary driver (nvidia-dkms) has been removed from the Arch repos. '
				'Please use "Nvidia (open kernel module for newer GPUs, Turing+)" instead.'
			)

		return cls(
			profile,
			GfxDriver(gfx_driver) if gfx_driver else None,
			GreeterType(greeter) if greeter else None,
		)
