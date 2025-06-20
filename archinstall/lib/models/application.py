from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any, NotRequired, TypedDict


class BluetoothConfigSerialization(TypedDict):
	enabled: bool


class Audio(StrEnum):
	NO_AUDIO = 'No audio server'
	PIPEWIRE = auto()
	PULSEAUDIO = auto()


class AudioConfigSerialization(TypedDict):
	audio: str


class ApplicationSerialization(TypedDict):
	bluetooth_config: NotRequired[BluetoothConfigSerialization]
	audio_config: NotRequired[AudioConfigSerialization]


@dataclass
class AudioConfiguration:
	audio: Audio

	def json(self) -> AudioConfigSerialization:
		return {
			'audio': self.audio.value,
		}

	@staticmethod
	def parse_arg(arg: dict[str, Any]) -> 'AudioConfiguration':
		return AudioConfiguration(
			Audio(arg['audio']),
		)


@dataclass
class BluetoothConfiguration:
	enabled: bool

	def json(self) -> BluetoothConfigSerialization:
		return {'enabled': self.enabled}

	@staticmethod
	def parse_arg(arg: dict[str, Any]) -> 'BluetoothConfiguration':
		return BluetoothConfiguration(arg['enabled'])


@dataclass
class ApplicationConfiguration:
	bluetooth_config: BluetoothConfiguration | None = None
	audio_config: AudioConfiguration | None = None

	@staticmethod
	def parse_arg(
		args: dict[str, Any] | None = None,
		old_audio_config: dict[str, Any] | None = None,
	) -> 'ApplicationConfiguration':
		app_config = ApplicationConfiguration()

		if args and (bluetooth_config := args.get('bluetooth_config')) is not None:
			app_config.bluetooth_config = BluetoothConfiguration.parse_arg(bluetooth_config)

		# deprecated: backwards compatibility
		if old_audio_config is not None:
			app_config.audio_config = AudioConfiguration.parse_arg(old_audio_config)

		if args and (audio_config := args.get('audio_config')) is not None:
			app_config.audio_config = AudioConfiguration.parse_arg(audio_config)

		return app_config

	def json(self) -> ApplicationSerialization:
		config: ApplicationSerialization = {}

		if self.bluetooth_config:
			config['bluetooth_config'] = self.bluetooth_config.json()

		if self.audio_config:
			config['audio_config'] = self.audio_config.json()

		return config
