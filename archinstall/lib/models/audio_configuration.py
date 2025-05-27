from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING

from ..hardware import SysInfo
from ..output import info

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class Audio(StrEnum):
	NO_AUDIO = 'No audio server'
	PIPEWIRE = auto()
	PULSEAUDIO = auto()


@dataclass
class AudioConfiguration:
	audio: Audio

	def json(self) -> dict[str, str]:
		return {
			'audio': self.audio.value,
		}

	@staticmethod
	def parse_arg(arg: dict[str, str]) -> 'AudioConfiguration':
		return AudioConfiguration(
			Audio(arg['audio']),
		)

	def install_audio_config(
		self,
		installation: 'Installer',
	) -> None:
		info(f'Installing audio server: {self.audio.name}')

		from ...default_profiles.applications.pipewire import PipewireProfile

		match self.audio:
			case Audio.PIPEWIRE:
				PipewireProfile().install(installation)
			case Audio.PULSEAUDIO:
				installation.add_additional_packages('pulseaudio')

		if self.audio != Audio.NO_AUDIO:
			if SysInfo.requires_sof_fw():
				installation.add_additional_packages('sof-firmware')

			if SysInfo.requires_alsa_fw():
				installation.add_additional_packages('alsa-firmware')
