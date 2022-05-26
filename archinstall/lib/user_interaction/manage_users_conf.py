from __future__ import annotations

import re
from typing import Any, Dict, TYPE_CHECKING, List, Optional

from .utils import get_password
from ..menu import Menu
from ..menu.list_manager import ListManager
from ..models.users import User

if TYPE_CHECKING:
	_: Any


class UserList(ListManager):
	"""
	subclass of ListManager for the managing of user accounts
	"""

	def __init__(self, prompt: str, lusers: List[User]):
		"""
		param: prompt
		type: str
		param: lusers dict with the users already defined for the system
		type: Dict
		param: sudo. boolean to determine if we handle superusers or users. If None handles both types
		"""
		self._actions = [
			str(_('Add a user')),
			str(_('Change password')),
			str(_('Promote/Demote user')),
			str(_('Delete User'))
		]
		super().__init__(prompt, lusers, self._actions, self._actions[0])

	def reformat(self, data: List[User]) -> Dict[str, User]:
		return {e.display(): e for e in data}

	def action_list(self):
		active_user = self.target if self.target else None

		if active_user is None:
			return [self._actions[0]]
		else:
			return self._actions[1:]

	def exec_action(self, data: List[User]) -> List[User]:
		if self.target:
			active_user = self.target
		else:
			active_user = None

		if self.action == self._actions[0]:  # add
			new_user = self._add_user()
			if new_user is not None:
				# in case a user with the same username as an existing user
				# was created we'll replace the existing one
				data = [d for d in data if d.username != new_user.username]
				data += [new_user]
		elif self.action == self._actions[1]:  # change password
			prompt = str(_('Password for user "{}": ').format(active_user.username))
			new_password = get_password(prompt=prompt)
			if new_password:
				user = next(filter(lambda x: x == active_user, data), 1)
				user.password = new_password
		elif self.action == self._actions[2]:  # promote/demote
			user = next(filter(lambda x: x == active_user, data), 1)
			user.sudo = False if user.sudo else True
		elif self.action == self._actions[3]:  # delete
			data = [d for d in data if d != active_user]

		return data

	def _check_for_correct_username(self, username: str) -> bool:
		if re.match(r'^[a-z_][a-z0-9_-]*\$?$', username) and len(username) <= 32:
			return True
		return False

	def _add_user(self) -> Optional[User]:
		print(_('\nDefine a new user\n'))
		prompt = str(_('Enter username (leave blank to skip): '))

		while True:
			username = input(prompt).strip(' ')
			if not username:
				return None
			if not self._check_for_correct_username(username):
				prompt = str(_("The username you entered is invalid. Try again")) + '\n' + prompt
			else:
				break

		password = get_password(prompt=str(_('Password for user "{}": ').format(username)))

		choice = Menu(
			str(_('Should "{}" be a superuser (sudo)?')).format(username), Menu.yes_no(),
			skip=False,
			default_option=Menu.no()
		).run()

		sudo = True if choice.value == Menu.yes() else False
		return User(username, password, sudo)


def ask_for_additional_users(prompt: str = '', defined_users: List[User] = []) -> List[User]:
	prompt = prompt if prompt else _('Enter username (leave blank to skip): ')
	users = UserList(prompt, defined_users).run()
	return users
