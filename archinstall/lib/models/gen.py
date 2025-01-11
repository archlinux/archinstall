from dataclasses import dataclass
from typing import Any, override


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
			results=results
		)


@dataclass
class LocalPackage:
	name: str
	version: str
	description: str
	architecture: str
	url: str
	licenses: str
	groups: str
	depends_on: str
	optional_deps: str
	required_by: str
	optional_for: str
	conflicts_with: str
	replaces: str
	installed_size: str
	packager: str
	build_date: str
	install_date: str
	install_reason: str
	install_script: str
	validated_by: str
	provides: str

	@property
	def pkg_version(self) -> str:
		return self.version

	@override
	def __eq__(self, other: object) -> bool:
		if not isinstance(other, LocalPackage):
			return NotImplemented

		return self.pkg_version == other.pkg_version

	def __lt__(self, other: 'LocalPackage') -> bool:
		return self.pkg_version < other.pkg_version
