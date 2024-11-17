from dataclasses import dataclass
from typing import Any


@dataclass
class VersionDef:
	version_string: str

	@classmethod
	def parse_version(cls) -> list[str]:
		if '.' in cls.version_string:
			versions = cls.version_string.split('.')
		else:
			versions = [cls.version_string]

		return versions

	@classmethod
	def major(self) -> str:
		return self.parse_version()[0]

	@classmethod
	def minor(cls) -> str | None:
		versions = cls.parse_version()
		if len(versions) >= 2:
			return versions[1]

		return None

	@classmethod
	def patch(cls) -> str | None:
		versions = cls.parse_version()
		if '-' in versions[-1]:
			_, patch_version = versions[-1].split('-', 1)
			return patch_version

		return None

	def __eq__(self, other) -> bool:
		if other.major == self.major and \
			other.minor == self.minor and \
			other.patch == self.patch:

			return True
		return False

	def __lt__(self, other) -> bool:
		if self.major() > other.major():
			return False
		elif self.minor() and other.minor() and self.minor() > other.minor():
			return False
		elif self.patch() and other.patch() and self.patch() > other.patch():
			return False

		return True

	def __str__(self) -> str:
		return self.version_string


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

	def __eq__(self, other) -> bool:
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

	def __eq__(self, other) -> bool:
		return self.pkg_version == other.pkg_version

	def __lt__(self, other: 'LocalPackage') -> bool:
		return self.pkg_version < other.pkg_version
