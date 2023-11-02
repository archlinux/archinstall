from __future__ import annotations

import re
from typing import Any, Dict, TYPE_CHECKING, List, Optional

from .utils import get_password
from ..menu import Menu, ListManager
from ..models.users import User
from ..output import FormattedOutput

if TYPE_CHECKING:
	_: Any


class UserList(ListManager):
	"""
	subclass of ListManager for the managing of user accounts
	"""

	def __init__(self, prompt: str, lusers: List[User]):
		self._actions = [
			str(_('Add a user')),
			str(_('Change password')),
			str(_('Promote/Demote user')),
			str(_('Delete User'))
		]
		super().__init__(prompt, lusers, [self._actions[0]], self._actions[1:])

	def reformat(self, data: List[User]) -> Dict[str, Any]:
		table = FormattedOutput.as_table(data)
		rows = table.split('\n')

		# these are the header rows of the table and do not map to any User obviously
		# we're adding 2 spaces as prefix because the menu selector '> ' will be put before
		# the selectable rows so the header has to be aligned
		display_data: Dict[str, Optional[User]] = {f'  {rows[0]}': None, f'  {rows[1]}': None}

		for row, user in zip(rows[2:], data):
			row = row.replace('|', '\\|')
			display_data[row] = user

		return display_data

	def selected_action_display(self, user: User) -> str:
		return user.username

	def handle_action(self, action: str, entry: Optional[User], data: List[User]) -> List[User]:
		if action == self._actions[0]:  # add
			new_user = self._add_user()
			if new_user is not None:
				# in case a user with the same username as an existing user
				# was created we'll replace the existing one
				data = [d for d in data if d.username != new_user.username]
				data += [new_user]
		elif action == self._actions[1] and entry:  # change password
			prompt = str(_('Password for user "{}": ').format(entry.username))
			new_password = get_password(prompt=prompt)
			if new_password:
				user = next(filter(lambda x: x == entry, data))
				user.password = new_password
		elif action == self._actions[2] and entry:  # promote/demote
			user = next(filter(lambda x: x == entry, data))
			user.sudo = False if user.sudo else True
		elif action == self._actions[3] and entry:  # delete
			data = [d for d in data if d != entry]

		return data

	def _check_for_correct_username(self, username: str) -> bool:
		if re.match(r'^[a-z_][a-z0-9_-]*\$?$', username) and len(username) <= 32:
			return True
		return False

	def _add_user(self) -> Optional[User]:
		prompt = '\n\n' + str(_('Enter username (leave blank to skip): '))

		while True:
			try:
				username = input(prompt).strip(' ')
			except (KeyboardInterrupt, EOFError):
				return None

			if not username:
				return None
			if not self._check_for_correct_username(username):
				error_prompt = str(_("The username you entered is invalid. Try again"))
				print(error_prompt)
			else:
				break

		password = get_password(prompt=str(_('Password for user "{}": ').format(username)))

		if not password:
			return None

		choice = Menu(
			str(_('Should "{}" be a superuser (sudo)?')).format(username), Menu.yes_no(),
			skip=False,
			default_option=Menu.yes(),
			clear_screen=False,
			show_search_hint=False
		).run()

		sudo = True if choice.value == Menu.yes() else False
		return User(username, password, sudo)


def ask_for_additional_users(prompt: str = '', defined_users: List[User] = []) -> List[User]:
	users = UserList(prompt, defined_users).run()
	return users
