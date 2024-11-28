from dataclasses import dataclass
from enum import Enum

from ...default_profiles.applications.pipewire import PipewireProfile
from ..hardware import SysInfo
from ..installer import Installer
from ..output import info


@dataclass
class Audio(Enum):
	NoAudio = 'No audio server'
	Pipewire = 'pipewire'
	Pulseaudio = 'pulseaudio'


@dataclass
class AudioConfiguration:
	audio: Audio

	def json(self) -> dict[str, str]:
		return {
			'audio': self.audio.value
		}

	@staticmethod
	def parse_arg(arg: dict[str, str]) -> 'AudioConfiguration':
		return AudioConfiguration(
			Audio(arg['audio'])
		)

	def install_audio_config(
		self,
		installation: Installer
	) -> None:
		info(f'Installing audio server: {self.audio.name}')

		match self.audio:
			case Audio.Pipewire:
				PipewireProfile().install(installation)
			case Audio.Pulseaudio:
				installation.add_additional_packages("pulseaudio")

		if self.audio != Audio.NoAudio:
			if SysInfo.requires_sof_fw():
				installation.add_additional_packages('sof-firmware')

			if SysInfo.requires_alsa_fw():
				installation.add_additional_packages('alsa-firmware')
