from dataclasses import dataclass
from enum import Enum
from typing import Any, TYPE_CHECKING, Dict

from ..hardware import SysInfo
from ..output import info
from ...default_profiles.applications.pipewire import PipewireProfile

if TYPE_CHECKING:
	_: Any


@dataclass
class Audio(Enum):
	Pipewire = 'pipewire'
	Pulseaudio = 'pulseaudio'

	@staticmethod
	def no_audio_text() -> str:
		return str(_('No audio server'))


@dataclass
class AudioConfiguration:
	audio: Audio

	def json(self) -> Dict[str, Any]:
		return {
			'audio': self.audio.value
		}

	@staticmethod
	def parse_arg(arg: Dict[str, Any]) -> 'AudioConfiguration':
		return AudioConfiguration(
			Audio(arg['audio'])
		)

	def install_audio_config(
		self,
		installation: Any
	):
		info(f'Installing audio server: {self.audio.name}')

		match self.audio:
			case Audio.Pipewire:
				PipewireProfile().install(installation)
			case Audio.Pulseaudio:
				installation.add_additional_packages("pulseaudio")

		if SysInfo.requires_sof_fw():
			installation.add_additional_packages('sof-firmware')

		if SysInfo.requires_alsa_fw():
			installation.add_additional_packages('alsa-firmware')
