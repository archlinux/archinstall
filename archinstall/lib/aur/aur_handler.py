from typing import TYPE_CHECKING

from archinstall.applications.aur_helper import AURHelperApp
from archinstall.lib.exceptions import RequirementError
from archinstall.lib.models.aur import AURConfiguration
from archinstall.lib.models.users import User
from archinstall.lib.output import debug
from archinstall.lib.translationhandler import tr

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class AURHandler:
	"""Coordinates AUR helper installation as part of a guided install.

	The build user is resolved deterministically: first user with ``sudo=True``,
	falling back to the first user in ``users``. If no users are configured the
	handler raises ``RequirementError`` so ``--silent`` runs surface the missing
	dependency immediately.
	"""

	def install_aur(
		self,
		install_session: Installer,
		aur_config: AURConfiguration | None,
		users: list[User],
	) -> None:
		if aur_config is None or aur_config.helper_config is None:
			debug('AUR: no helper configured, skipping')
			return

		build_user = next((u for u in users if u.sudo), None) or (users[0] if users else None)

		if build_user is None:
			raise RequirementError(
				tr('AUR helper requires a non-root user account. Configure one under Authentication.'),
			)

		AURHelperApp().install(install_session, aur_config.helper_config, build_user)
