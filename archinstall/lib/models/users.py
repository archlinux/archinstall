from dataclasses import dataclass
from typing import Dict, List, Union, Any, TYPE_CHECKING

from .password_strength import PasswordStrength

if TYPE_CHECKING:
	_: Any


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

	def display(self) -> str:
		password = '*' * (len(self.password) if self.password else 0)
		if password:
			strength = PasswordStrength.strength(self.password)
			password += f' ({strength.value})'
		return f'{_("Username")}: {self.username:16} {_("Password")}: {password:20} sudo: {str(self.sudo)}'

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
