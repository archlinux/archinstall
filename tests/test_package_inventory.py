import ast
from enum import StrEnum
from pathlib import Path

import pytest

from archinstall.default_profiles.profile import CustomSetting, Profile, ProfileType
from archinstall.lib.applications import application_handler
from archinstall.lib.models.package_types import InstallationPackage
from archinstall.lib.packages import meta
from archinstall.lib.profile.profiles_handler import ProfileHandler


def test_committed_source_targets() -> None:
	assert meta.PKGBUILD.read_text() == meta.render(), 'Run python -m archinstall.lib.packages.meta'


def test_conditional_package_choices() -> None:
	targets = meta.package_targets()
	assert {'seatd', 'polkit', 'plasma', 'plasma-meta', 'plasma-desktop'} <= targets
	assert {'amd-ucode', 'intel-ucode', 'linux-lts-headers', 'btrfs-progs', 'brltty', 'network-manager-applet', 'dms-shell'} <= targets
	assert {'linux-firmware-qcom', 'linux-firmware-mellanox'} <= targets


def test_profile_settings_are_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
	profile = Profile('New', ProfileType.Custom, packages=['new-profile'])
	profile.custom_settings = {CustomSetting.SeatAccess: 'seatd'}
	monkeypatch.setattr(ProfileHandler, 'profiles', property(lambda _self: [profile]))
	before = profile.custom_settings.copy()
	assert 'new-profile' in meta.package_targets()
	assert profile.custom_settings == before


def test_new_sources_are_discovered(monkeypatch: pytest.MonkeyPatch) -> None:
	before = meta.package_targets()
	profiles = [*ProfileHandler().profiles, Profile('New', ProfileType.Custom, packages=['new-profile'])]
	monkeypatch.setattr(ProfileHandler, 'profiles', property(lambda _self: profiles))

	class NewApp:
		@property
		def packages(self) -> list[str]:
			return ['new-app']

	NewApp.__module__ = 'archinstall.applications.new'
	monkeypatch.setattr(application_handler, 'NewApp', NewApp, raising=False)
	choices = {package.name: package.value for package in InstallationPackage} | {'NEW': 'new-choice'}
	monkeypatch.setattr(meta, 'InstallationPackage', StrEnum('NewPackages', choices))
	assert meta.package_targets() == before | {'new-profile', 'new-app', 'new-choice'}


def test_new_setting_requires_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.delitem(meta.PROFILE_SETTINGS, CustomSetting.SeatAccess)
	with pytest.raises(ValueError, match='missing custom settings'):
		meta.package_targets()


def is_package_list(node: ast.AST) -> bool:
	return (isinstance(node, ast.Name) and node.id == 'packages') or (isinstance(node, ast.Attribute) and node.attr == '_base_packages')


def literal_installations(tree: ast.AST) -> list[int]:
	roots: list[ast.AST] = []
	for node in ast.walk(tree):
		if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
			if node.func.attr in {'strap', 'add_additional_packages'} or (is_package_list(node.func.value) and node.func.attr in {'append', 'extend'}):
				roots.extend(node.args)
				roots.extend(keyword.value for keyword in node.keywords if keyword.arg == 'packages')
		elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
			getter = node.name == 'packages' or node.name.endswith('_packages')
			if getter and any(isinstance(decorator, ast.Name) and decorator.id == 'property' for decorator in node.decorator_list):
				continue
			for child in ast.walk(node):
				if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
					targets = child.targets if isinstance(child, ast.Assign) else [child.target]
					if any(is_package_list(target) for target in targets) and isinstance(child.value, (ast.List, ast.Tuple, ast.Set, ast.Constant)):
						roots.append(child.value)
	return [node.lineno for root in roots for node in ast.walk(root) if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def test_installation_literals_use_metadata() -> None:
	root = Path(__file__).resolve().parents[1] / 'archinstall'
	trees = {str(path.relative_to(root)): ast.parse(path.read_text()) for path in root.rglob('*.py')}
	violations = {path: lines for path, tree in trees.items() if (lines := literal_installations(tree))}
	assert not violations, f'Use InstallationPackage for package selections: {violations}'
	used = {
		node.attr
		for tree in trees.values()
		for node in ast.walk(tree)
		if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'InstallationPackage'
	}
	assert used == set(InstallationPackage.__members__), 'Remove unused InstallationPackage entries'


@pytest.mark.parametrize(
	'source',
	[
		"installer.add_additional_packages(['new'])",
		"pacman.strap('new')",
		"def install():\n packages = ['new']\n installer.add_additional_packages(packages)",
		"packages.append('new')",
		"installer.add_additional_packages(packages=['new'])",
		"def install():\n packages: list[str] = ['new']",
		"def install():\n packages += ['new']",
		"def install(self):\n self._base_packages += ['new']",
		"def install_packages():\n packages = ['new']",
	],
)
def test_new_literal_is_rejected(source: str) -> None:
	assert literal_installations(ast.parse(source))
