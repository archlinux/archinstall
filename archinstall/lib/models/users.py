from dataclasses import dataclass, field
from enum import Enum
from typing import NotRequired, TypedDict, override

from archinstall.lib.translationhandler import tr

from ..crypt import crypt_yescrypt


class PasswordStrength(Enum):
	VERY_WEAK = 'very weak'
	WEAK = 'weak'
	MODERATE = 'moderate'
	STRONG = 'strong'

	@property
	@override
	def value(self) -> str:  # pylint: disable=invalid-overridden-method
		match self:
			case PasswordStrength.VERY_WEAK:
				return tr('very weak')
			case PasswordStrength.WEAK:
				return tr('weak')
			case PasswordStrength.MODERATE:
				return tr('moderate')
			case PasswordStrength.STRONG:
				return tr('strong')

	def color(self) -> str:
		match self:
			case PasswordStrength.VERY_WEAK:
				return 'red'
			case PasswordStrength.WEAK:
				return 'red'
			case PasswordStrength.MODERATE:
				return 'yellow'
			case PasswordStrength.STRONG:
				return 'green'

	@classmethod
	def strength(cls, password: str) -> 'PasswordStrength':
		digit = any(character.isdigit() for character in password)
		upper = any(character.isupper() for character in password)
		lower = any(character.islower() for character in password)
		symbol = any(not character.isalnum() for character in password)
		return cls._check_password_strength(digit, upper, lower, symbol, len(password))

	@classmethod
	def _check_password_strength(
		cls,
		digit: bool,
		upper: bool,
		lower: bool,
		symbol: bool,
		length: int,
	) -> 'PasswordStrength':
		# suggested evaluation
		# https://github.com/archlinux/archinstall/issues/1304#issuecomment-1146768163
		if digit and upper and lower and symbol:
			match length:
				case num if 13 <= num:
					return PasswordStrength.STRONG
				case num if 11 <= num <= 12:
					return PasswordStrength.MODERATE
				case num if 7 <= num <= 10:
					return PasswordStrength.WEAK
				case num if num <= 6:
					return PasswordStrength.VERY_WEAK
		elif digit and upper and lower:
			match length:
				case num if 14 <= num:
					return PasswordStrength.STRONG
				case num if 11 <= num <= 13:
					return PasswordStrength.MODERATE
				case num if 7 <= num <= 10:
					return PasswordStrength.WEAK
				case num if num <= 6:
					return PasswordStrength.VERY_WEAK
		elif upper and lower:
			match length:
				case num if 15 <= num:
					return PasswordStrength.STRONG
				case num if 12 <= num <= 14:
					return PasswordStrength.MODERATE
				case num if 7 <= num <= 11:
					return PasswordStrength.WEAK
				case num if num <= 6:
					return PasswordStrength.VERY_WEAK
		elif lower or upper:
			match length:
				case num if 18 <= num:
					return PasswordStrength.STRONG
				case num if 14 <= num <= 17:
					return PasswordStrength.MODERATE
				case num if 9 <= num <= 13:
					return PasswordStrength.WEAK
				case num if num <= 8:
					return PasswordStrength.VERY_WEAK

		return PasswordStrength.VERY_WEAK


UserSerialization = TypedDict(
	'UserSerialization',
	{
		'username': str,
		'!password': NotRequired[str],
		'sudo': bool,
		'groups': list[str],
		'enc_password': str | None,
	},
)


class Password:
	def __init__(
		self,
		plaintext: str = '',
		enc_password: str | None = None,
	):
		if plaintext:
			enc_password = crypt_yescrypt(plaintext)

		if not plaintext and not enc_password:
			raise ValueError('Either plaintext or enc_password must be provided')

		self._plaintext = plaintext
		self.enc_password = enc_password

	@property
	def plaintext(self) -> str:
		return self._plaintext

	@plaintext.setter
	def plaintext(self, value: str) -> None:
		self._plaintext = value
		self.enc_password = crypt_yescrypt(value)

	@override
	def __eq__(self, other: object) -> bool:
		if not isinstance(other, Password):
			return NotImplemented

		if self._plaintext and other._plaintext:
			return self._plaintext == other._plaintext

		return self.enc_password == other.enc_password

	def hidden(self) -> str:
		if self._plaintext:
			return '*' * len(self._plaintext)
		else:
			return '*' * 8


@dataclass
class User:
	username: str
	password: Password
	sudo: bool
	groups: list[str] = field(default_factory=list)

	@override
	def __str__(self) -> str:
		# safety overwrite to make sure password is not leaked
		return f'User({self.username=}, {self.sudo=}, {self.groups=})'

	def table_data(self) -> dict[str, str | bool | list[str]]:
		return {
			'username': self.username,
			'password': self.password.hidden(),
			'sudo': self.sudo,
			'groups': self.groups,
		}

	def json(self) -> UserSerialization:
		return {
			'username': self.username,
			'enc_password': self.password.enc_password,
			'sudo': self.sudo,
			'groups': self.groups,
		}

	@classmethod
	def parse_arguments(
		cls,
		args: list[UserSerialization],
	) -> list['User']:
		users: list[User] = []

		for entry in args:
			username = entry.get('username')
			password: Password | None = None
			groups = entry.get('groups', [])
			plaintext = entry.get('!password')
			enc_password = entry.get('enc_password')

			# DEPRECATED: backwards compatibility
			if plaintext:
				password = Password(plaintext=plaintext)
			elif enc_password:
				password = Password(enc_password=enc_password)

			if username is None or password is None:
				continue

			user = User(
				username=username,
				password=password,
				sudo=entry.get('sudo', False) is True,
				groups=groups,
			)

			users.append(user)

		return users
