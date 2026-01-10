from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any, NotRequired, TypedDict


class PowerManagement(StrEnum):
	POWER_PROFILES_DAEMON = 'power-profiles-daemon'
	TUNED = 'tuned'


class PowerManagementConfigSerialization(TypedDict):
	power_management: str


class BluetoothConfigSerialization(TypedDict):
	enabled: bool


class Audio(StrEnum):
	NO_AUDIO = 'No audio server'
	PIPEWIRE = auto()
	PULSEAUDIO = auto()


class AudioConfigSerialization(TypedDict):
	audio: str


class PrintServiceConfigSerialization(TypedDict):
	enabled: bool


class Firewall(StrEnum):
	UFW = 'ufw'
	FWD = 'firewalld'


class FirewallConfigSerialization(TypedDict):
	firewall: str


class ZramAlgorithm(StrEnum):
	ZSTD = 'zstd'
	LZO_RLE = 'lzo-rle'
	LZO = 'lzo'
	LZ4 = 'lz4'
	LZ4HC = 'lz4hc'


class ApplicationSerialization(TypedDict):
	bluetooth_config: NotRequired[BluetoothConfigSerialization]
	audio_config: NotRequired[AudioConfigSerialization]
	power_management_config: NotRequired[PowerManagementConfigSerialization]
	print_service_config: NotRequired[PrintServiceConfigSerialization]
	firewall_config: NotRequired[FirewallConfigSerialization]


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
	def parse_arg(arg: BluetoothConfigSerialization) -> 'BluetoothConfiguration':
		return BluetoothConfiguration(arg['enabled'])


@dataclass
class PowerManagementConfiguration:
	power_management: PowerManagement

	def json(self) -> PowerManagementConfigSerialization:
		return {
			'power_management': self.power_management.value,
		}

	@staticmethod
	def parse_arg(arg: PowerManagementConfigSerialization) -> 'PowerManagementConfiguration':
		return PowerManagementConfiguration(
			PowerManagement(arg['power_management']),
		)


@dataclass
class PrintServiceConfiguration:
	enabled: bool

	def json(self) -> PrintServiceConfigSerialization:
		return {'enabled': self.enabled}

	@staticmethod
	def parse_arg(arg: PrintServiceConfigSerialization) -> 'PrintServiceConfiguration':
		return PrintServiceConfiguration(arg['enabled'])


@dataclass
class FirewallConfiguration:
	firewall: Firewall

	def json(self) -> FirewallConfigSerialization:
		return {
			'firewall': self.firewall.value,
		}

	@staticmethod
	def parse_arg(arg: dict[str, Any]) -> 'FirewallConfiguration':
		return FirewallConfiguration(
			Firewall(arg['firewall']),
		)


@dataclass(frozen=True)
class ZramConfiguration:
	enabled: bool
	algorithm: ZramAlgorithm = ZramAlgorithm.ZSTD

	@staticmethod
	def parse_arg(arg: bool | dict[str, Any]) -> 'ZramConfiguration':
		if isinstance(arg, bool):
			return ZramConfiguration(enabled=arg)

		enabled = arg.get('enabled', True)
		algo = arg.get('algorithm', arg.get('algo', ZramAlgorithm.ZSTD.value))
		return ZramConfiguration(enabled=enabled, algorithm=ZramAlgorithm(algo))


@dataclass
class ApplicationConfiguration:
	bluetooth_config: BluetoothConfiguration | None = None
	audio_config: AudioConfiguration | None = None
	power_management_config: PowerManagementConfiguration | None = None
	print_service_config: PrintServiceConfiguration | None = None
	firewall_config: FirewallConfiguration | None = None

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

		if args and (power_management_config := args.get('power_management_config')) is not None:
			app_config.power_management_config = PowerManagementConfiguration.parse_arg(power_management_config)

		if args and (print_service_config := args.get('print_service_config')) is not None:
			app_config.print_service_config = PrintServiceConfiguration.parse_arg(print_service_config)

		if args and (firewall_config := args.get('firewall_config')) is not None:
			app_config.firewall_config = FirewallConfiguration.parse_arg(firewall_config)

		return app_config

	def json(self) -> ApplicationSerialization:
		config: ApplicationSerialization = {}

		if self.bluetooth_config:
			config['bluetooth_config'] = self.bluetooth_config.json()

		if self.audio_config:
			config['audio_config'] = self.audio_config.json()

		if self.power_management_config:
			config['power_management_config'] = self.power_management_config.json()

		if self.print_service_config:
			config['print_service_config'] = self.print_service_config.json()

		if self.firewall_config:
			config['firewall_config'] = self.firewall_config.json()

		return config
