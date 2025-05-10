from dataclasses import dataclass
from enum import StrEnum, auto


class Audio(StrEnum):
	NO_AUDIO = 'No audio server'
	PIPEWIRE = auto()
	PULSEAUDIO = auto()


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
