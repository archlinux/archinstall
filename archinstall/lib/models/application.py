from dataclasses import dataclass
from typing import NotRequired, TypedDict


class BluetoothConfigSerialization(TypedDict):
	enabled: bool


class ApplicationSerialization(TypedDict):
	bluetooth_config: NotRequired[BluetoothConfigSerialization]


@dataclass
class BluetoothConfiguration:
	enabled: bool

	def json(self) -> BluetoothConfigSerialization:
		return {'enabled': self.enabled}

	@staticmethod
	def parse_arg(arg: BluetoothConfigSerialization) -> 'BluetoothConfiguration':
		return BluetoothConfiguration(arg['enabled'])


@dataclass
class ApplicationConfiguration:
	bluetooth_config: BluetoothConfiguration | None = None

	@staticmethod
	def parse_arg(args: ApplicationSerialization) -> 'ApplicationConfiguration':
		bluetooth_config: BluetoothConfiguration | None = None
		if 'bluetooth_config' in args:
			bluetooth_config = BluetoothConfiguration.parse_arg(args['bluetooth_config'])

		return ApplicationConfiguration(
			bluetooth_config=bluetooth_config,
		)

	def json(self) -> ApplicationSerialization:
		config: ApplicationSerialization = {}

		if self.bluetooth_config:
			config['bluetooth_config'] = self.bluetooth_config.json()

		return config
