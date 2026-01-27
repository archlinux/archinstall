from functools import lru_cache

from ..exceptions import SysCallError
from ..models.packages import AvailablePackage, LocalPackage, Repository
from ..output import debug
from ..pacman.pacman import Pacman


# TODO: This shouldn't be living in here but there are too many
# circular dependecies so they will need to be cleanup up first
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


def installed_package(package: str) -> LocalPackage | None:
	try:
		package_info = []
		for line in Pacman.run(f'-Q --info {package}'):
			package_info.append(line.decode().strip())

		return _parse_package_output(package_info, LocalPackage)
	except SysCallError:
		pass

	return None


@lru_cache
def check_package_upgrade(package: str) -> str | None:
	try:
		for line in Pacman.run(f'-Qu {package}'):
			return line.decode().strip()
	except SysCallError:
		debug(f'Failed to check for package upgrades: {package}')

	return None


@lru_cache
def list_available_packages(
	repositories: tuple[Repository, ...],
) -> dict[str, AvailablePackage]:
	"""
	Returns a list of all available packages in the database
	"""
	packages: dict[str, AvailablePackage] = {}
	current_package: list[str] = []
	filtered_repos = [repo.value for repo in repositories]

	try:
		Pacman.run('-Sy')
	except Exception as e:
		debug(f'Failed to sync Arch Linux package database: {e}')

	for line in Pacman.run('-S --info'):
		dec_line = line.decode().strip()
		current_package.append(dec_line)

		if dec_line.startswith('Validated'):
			if current_package:
				avail_pkg = _parse_package_output(current_package, AvailablePackage)
				if avail_pkg.repository in filtered_repos:
					packages[avail_pkg.name] = avail_pkg
				current_package = []

	return packages


@lru_cache(maxsize=128)
def _normalize_key_name(key: str) -> str:
	return key.strip().lower().replace(' ', '_')


def _parse_package_output[PackageType: (AvailablePackage, LocalPackage)](
	package_meta: list[str],
	cls: type[PackageType],
) -> PackageType:
	package = {}

	for line in package_meta:
		if ':' in line:
			key, value = line.split(':', 1)
			key = _normalize_key_name(key)
			package[key] = value.strip()

	return cls.model_validate(package)
