from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING, List, Optional

from ..utils.util import get_password
from ..menu import ListManager
from ..models.users import User
from ..general import secret

from archinstall.tui import (
	MenuItemGroup, MenuItem, SelectMenu,
	Alignment, EditMenu, Orientation
)

if TYPE_CHECKING:
	_: Any


class UserList(ListManager):
	def __init__(self, prompt: str, lusers: List[User]):
		self._actions = [
			str(_('Add a user')),
			str(_('Change password')),
			str(_('Promote/Demote user')),
			str(_('Delete User'))
		]
		super().__init__(prompt, lusers, [self._actions[0]], self._actions[1:])

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
			header = f'{str(_("User"))}: {entry.username}\n'
			new_password = get_password(str(_('Password')), header=header)

			if new_password:
				user = next(filter(lambda x: x == entry, data))
				user.password = new_password
		elif action == self._actions[2] and entry:  # promote/demote
			user = next(filter(lambda x: x == entry, data))
			user.sudo = False if user.sudo else True
		elif action == self._actions[3] and entry:  # delete
			data = [d for d in data if d != entry]

		return data

	def _check_for_correct_username(self, username: str) -> Optional[str]:
		if re.match(r'^[a-z_][a-z0-9_-]*\$?$', username) and len(username) <= 32:
			return None
		return str(_("The username you entered is invalid"))

	def _add_user(self) -> Optional[User]:
		user_res = EditMenu(
			str(_('Username')),
			allow_skip=True,
			validator=self._check_for_correct_username
		).input()

		if not user_res.item:
			return None

		username = user_res.item
		header = f'{str(_("Username"))}: {username}\n'

		password = get_password(str(_('Password')), header=header, allow_skip=True)

		if not password:
			return None

		header += f'{str(_("Password"))}: {secret(password)}\n\n'
		header += str(_('Should "{}" be a superuser (sudo)?\n')).format(username)

		group = MenuItemGroup.yes_no()
		group.focus_item = MenuItem.yes()

		result = SelectMenu(
			group,
			header=header,
			alignment=Alignment.CENTER,
			columns=2,
			orientation=Orientation.HORIZONTAL,
			search_enabled=False,
			allow_skip=False
		).single()

		if result.item is None:
			return None

		sudo = True if result.item == MenuItem.yes() else False
		return User(username, password, sudo)


def ask_for_additional_users(prompt: str = '', defined_users: List[User] = []) -> List[User]:
	users = UserList(prompt, defined_users).run()
	return users
