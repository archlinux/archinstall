from functools import lru_cache

from archinstall.lib.menu.helpers import Loading, Notify, Selection
from archinstall.lib.models.packages import AvailablePackage, LocalPackage, PackageGroup, Repository
from archinstall.lib.translationhandler import tr
from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.ui.result import ResultType

from ..exceptions import SysCallError
from ..output import debug
from ..pacman.pacman import Pacman


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


def select_additional_packages(
	preset: list[str] = [],
	repositories: set[Repository] = set(),
) -> list[str]:
	repositories |= {Repository.Core, Repository.Extra}

	respos_text = ', '.join(r.value for r in repositories)
	output = tr('Repositories: {}').format(respos_text) + '\n'
	output += tr('Loading packages...')

	result = Loading[dict[str, AvailablePackage]](
		header=output,
		data_callback=lambda: list_available_packages(tuple(repositories)),
	).show()

	if result.type_ != ResultType.Selection:
		debug('Error while loading packages')
		return preset

	packages = result.get_value()

	if not packages:
		Notify(tr('No packages found')).show()
		return []

	package_groups = PackageGroup.from_available_packages(packages)

	# Additional packages (with some light weight error handling for invalid package names)
	header = tr('Only packages such as base, sudo, linux, linux-firmware, efibootmgr and optional profile packages are installed.') + '\n'
	header += tr('Note: base-devel is no longer installed by default. Add it here if you need build tools.') + '\n'
	header += tr('Select any packages from the below list that should be installed additionally') + '\n'

	# there are over 15k packages so this needs to be quick
	preset_packages: list[AvailablePackage | PackageGroup] = []
	for p in preset:
		if p in packages:
			preset_packages.append(packages[p])
		elif p in package_groups:
			preset_packages.append(package_groups[p])

	items = [
		MenuItem(
			name,
			value=pkg,
			preview_action=lambda x: x.value.info() if x.value else None,
		)
		for name, pkg in packages.items()
	]

	items += [
		MenuItem(
			name,
			value=group,
			preview_action=lambda x: x.value.info() if x.value else None,
		)
		for name, group in package_groups.items()
	]

	menu_group = MenuItemGroup(items, sort_items=True)
	menu_group.set_selected_by_value(preset_packages)

	pck_result = Selection[AvailablePackage | PackageGroup](
		menu_group,
		header=header,
		allow_reset=True,
		allow_skip=True,
		multi=True,
		preview_location='right',
		enable_filter=True,
	).show()

	match pck_result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return []
		case ResultType.Selection:
			selected_pacakges = pck_result.get_values()
			return [pkg.name for pkg in selected_pacakges]
