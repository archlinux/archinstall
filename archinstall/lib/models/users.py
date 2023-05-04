from dataclasses import dataclass
from typing import Dict, List, Union, Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
	_: Any


class PasswordStrength(Enum):
	VERY_WEAK = 'very weak'
	WEAK = 'weak'
	MODERATE = 'moderate'
	STRONG = 'strong'

	@property
	def value(self):
		match self:
			case PasswordStrength.VERY_WEAK: return str(_('very weak'))
			case PasswordStrength.WEAK: return str(_('weak'))
			case PasswordStrength.MODERATE: return str(_('moderate'))
			case PasswordStrength.STRONG: return str(_('strong'))

	def color(self):
		match self:
			case PasswordStrength.VERY_WEAK: return 'red'
			case PasswordStrength.WEAK: return 'red'
			case PasswordStrength.MODERATE: return 'yellow'
			case PasswordStrength.STRONG: return 'green'

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
		length: int
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


@dataclass
class User:
	username: str
	password: str
	sudo: bool

	@property
	def groups(self) -> List[str]:
		# this property should be transferred into a class attr instead
		# if it's every going to be used
		return []

	def json(self) -> Dict[str, Any]:
		return {
			'username': self.username,
			'!password': self.password,
			'sudo': self.sudo
		}

	@classmethod
	def _parse(cls, config_users: List[Dict[str, Any]]) -> List['User']:
		users = []

		for entry in config_users:
			username = entry.get('username', None)
			password = entry.get('!password', '')
			sudo = entry.get('sudo', False)

			if username is None:
				continue

			user = User(username, password, sudo)
			users.append(user)

		return users

	@classmethod
	def _parse_backwards_compatible(cls, config_users: Dict, sudo: bool) -> List['User']:
		if len(config_users.keys()) > 0:
			username = list(config_users.keys())[0]
			password = config_users[username]['!password']

			if password:
				return [User(username, password, sudo)]

		return []

	@classmethod
	def parse_arguments(
		cls,
		config_users: Union[List[Dict[str, str]], Dict[str, str]],
		config_superusers: Union[List[Dict[str, str]], Dict[str, str]]
	) -> List['User']:
		users = []

		# backwards compatibility
		if isinstance(config_users, dict):
			users += cls._parse_backwards_compatible(config_users, False)
		else:
			users += cls._parse(config_users)

		# backwards compatibility
		if isinstance(config_superusers, dict):
			users += cls._parse_backwards_compatible(config_superusers, True)

		return users
