from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import Any, override

from pydantic import BaseModel

from archinstall.lib.translationhandler import tr


class Repository(Enum):
	Core = 'core'
	Extra = 'extra'
	Multilib = 'multilib'
	Testing = 'testing'

	def get_repository_list(self) -> list[str]:
		match self:
			case Repository.Core:
				return [Repository.Core.value]
			case Repository.Extra:
				return [Repository.Extra.value]
			case Repository.Multilib:
				return [Repository.Multilib.value]
			case Repository.Testing:
				return [
					'core-testing',
					'extra-testing',
					'multilib-testing',
				]


@dataclass
class PackageSearchResult:
	pkgname: str
	pkgbase: str
	repo: str
	arch: str
	pkgver: str
	pkgrel: str
	epoch: int
	pkgdesc: str
	url: str
	filename: str
	compressed_size: int
	installed_size: int
	build_date: str
	last_update: str
	flag_date: str | None
	maintainers: list[str]
	packager: str
	groups: list[str]
	licenses: list[str]
	conflicts: list[str]
	provides: list[str]
	replaces: list[str]
	depends: list[str]
	optdepends: list[str]
	makedepends: list[str]
	checkdepends: list[str]

	@staticmethod
	def from_json(data: dict[str, Any]) -> 'PackageSearchResult':
		return PackageSearchResult(**data)

	@property
	def pkg_version(self) -> str:
		return self.pkgver

	@override
	def __eq__(self, other: object) -> bool:
		if not isinstance(other, PackageSearchResult):
			return NotImplemented

		return self.pkg_version == other.pkg_version

	def __lt__(self, other: 'PackageSearchResult') -> bool:
		return self.pkg_version < other.pkg_version


@dataclass
class PackageSearch:
	version: int
	limit: int
	valid: bool
	num_pages: int
	page: int
	results: list[PackageSearchResult]

	@staticmethod
	def from_json(data: dict[str, Any]) -> 'PackageSearch':
		results = [PackageSearchResult.from_json(r) for r in data['results']]

		return PackageSearch(
			version=data['version'],
			limit=data['limit'],
			valid=data['valid'],
			num_pages=data['num_pages'],
			page=data['page'],
			results=results,
		)


class LocalPackage(BaseModel):
	name: str
	version: str
	description: str
	architecture: str
	url: str
	licenses: str
	groups: str

	@override
	def __eq__(self, other: object) -> bool:
		if not isinstance(other, LocalPackage):
			return NotImplemented

		return self.version == other.version

	def __lt__(self, other: 'LocalPackage') -> bool:
		return self.version < other.version


class AvailablePackage(BaseModel):
	name: str
	architecture: str
	build_date: str
	depends_on: str
	description: str
	download_size: str
	groups: str
	installed_size: str
	licenses: str
	optional_deps: str
	packager: str
	provides: str
	replaces: str
	repository: str
	url: str
	validated_by: str
	version: str

	@cached_property
	def longest_key(self) -> int:
		return max(len(key) for key in self.model_dump().keys())

	# return all package info line by line
	def info(self) -> str:
		output = ''
		for key, value in self.model_dump().items():
			key = key.replace('_', ' ').capitalize()
			key = key.ljust(self.longest_key)
			output += f'{key} : {value}\n'

		return output


@dataclass
class PackageGroup:
	name: str
	packages: list[str] = field(default_factory=list)

	@classmethod
	def from_available_packages(
		cls,
		packages: dict[str, AvailablePackage],
	) -> dict[str, 'PackageGroup']:
		pkg_groups: dict[str, 'PackageGroup'] = {}

		for pkg in packages.values():
			if 'None' in pkg.groups:
				continue

			groups = pkg.groups.split(' ')

			for group in groups:
				# same group names have multiple spaces in between
				if len(group) == 0:
					continue

				pkg_groups.setdefault(group, PackageGroup(group))
				pkg_groups[group].packages.append(pkg.name)

		return pkg_groups

	def info(self) -> str:
		output = tr('Package group:') + '\n  - '
		output += '\n  - '.join(self.packages)
		return output
