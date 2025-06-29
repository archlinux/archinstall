from dataclasses import dataclass
from enum import Enum
from typing import Any, NotRequired, TypedDict

from archinstall.lib.translationhandler import tr


class AuthConfigSerialization(TypedDict):
	u2f_login_method: NotRequired[str]
	enable_sudo: bool


class AuthenticationSerialization(TypedDict):
	auth_config: NotRequired[AuthConfigSerialization]


class U2FLoginMethod(Enum):
	Passwordless = 'passwordless'
	SecondFactor = 'second_factor'

	def display_value(self) -> str:
		match self:
			case U2FLoginMethod.Passwordless:
				return tr('Passwordless login')
			case U2FLoginMethod.SecondFactor:
				return tr('Second factor login')
			case _:
				raise ValueError(f'Unknown type: {self}')


@dataclass
class U2FLoginConfiguration:
	u2f_login_method: U2FLoginMethod | None = None
	passwordless_sudo: bool = False

	def json(self) -> AuthConfigSerialization:
		config: AuthConfigSerialization = {
			'u2f_login_method': self.u2f_login_method.value if self.u2f_login_method else None,
			'passwordless_sudo': self.passwordless_sudo,
		}
		return config

	def parse_arg(args: dict[str, Any]) -> 'U2FLoginConfiguration':
		u2f_config = U2FLoginConfiguration()
		u2f_login_method = args.get('u2f_login_method')

		if u2f_login_method is None:
			return None

		u2f_config.u2f_login_method = U2FLoginMethod(u2f_login_method)

		if passwordless_sudo := args.get('passwordless_sudo') is not None:
			u2f_config.passwordless_sudo = passwordless_sudo

		return u2f_config


@dataclass
class AuthenticationConfiguration:
	u2f_config: U2FLoginConfiguration | None = None

	@staticmethod
	def parse_arg(args: dict[str, Any]) -> 'AuthenticationConfiguration':
		auth_config = AuthenticationConfiguration()

		if (u2f_config := args.get('u2f_config')) is not None:
			auth_config.u2f_config = U2FLoginConfiguration.parse_arg(u2f_config)

		return auth_config

	def json(self) -> AuthenticationSerialization:
		config: AuthenticationSerialization = {}

		if self.u2f_config:
			config['u2f_config'] = self.u2f_config.json()

		return config
