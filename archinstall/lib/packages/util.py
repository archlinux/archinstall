from functools import lru_cache

from archinstall.lib.output import debug
from archinstall.lib.packages.packages import check_package_upgrade


@lru_cache(maxsize=128)
def check_version_upgrade() -> str | None:
	debug('Checking version')
	upgrade = None

	upgrade = check_package_upgrade('archinstall')

	if upgrade is None:
		debug('No archinstall upgrades found')
		return None

	debug(f'Archinstall latest: {upgrade}')

	return upgrade
