from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

@dataclass
class VersionDef:
	version_string: str

	def parse_version(self) -> List[str]:
		if '.' in self.version_string:
			versions = self.version_string.split('.')
		else:
			versions = [self.version_string]

		return versions

	def major(self) -> str:
		return self.parse_version()[0]

	def minor(self) -> str:
		versions = self.parse_version()
		if len(versions) >= 2:
			return versions[1]

		return "0"

	def patch(self) -> str:
		versions = self.parse_version()
		if '-' in versions[-1]:
			_, patch_version = versions[-1].split('-', 1)
			return patch_version

		return "0"

	def __eq__(self, other :object) -> bool:
		if not isinstance(other, VersionDef):
			return NotImplemented

		if other.major() == self.major() and \
			other.minor() == self.minor() and \
			other.patch() == self.patch():

			return True
		return False
		
	def __lt__(self, other :object) -> bool:
		if not isinstance(other, VersionDef):
			return NotImplemented

		if self.major() < other.major():
			return False
		elif self.minor() and other.minor() and self.minor() > other.minor():
			return False
		elif self.patch() and other.patch() and self.patch() > other.patch():
			return False
		else:
			return True

	def __gt__(self, other :object) -> bool:
		if not isinstance(other, VersionDef):
			return NotImplemented

		if self.major() < other.major():
			return False
		elif self.minor() and other.minor() and self.minor() < other.minor():
			return False
		elif self.patch() and other.patch() and self.patch() < other.patch():
			return False
		else:
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
	flag_date: Optional[str]
	maintainers: List[str]
	packager: str
	groups: List[str]
	licenses: List[str]
	conflicts: List[str]
	provides: List[str]
	replaces: List[str]
	depends: List[str]
	optdepends: List[str]
	makedepends: List[str]
	checkdepends: List[str]

	@property
	def pkg_version(self) -> str:
		return self.pkgver

	def __eq__(self, other :object) -> bool:
		if not isinstance(other, PackageSearchResult):
			return NotImplemented

		return VersionDef(self.pkgver) == VersionDef(other.pkgver)

	def __lt__(self, other :object) -> bool:
		if not isinstance(other, PackageSearchResult):
			return NotImplemented

		return VersionDef(self.pkgver) < VersionDef(other.pkgver)


@dataclass
class PackageSearch:
	version: int
	limit: int
	valid: bool
	num_pages: int
	page: int
	results: List[PackageSearchResult]


@dataclass
class LocalPackage:
	name: str
	version: str
	description:str
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

	def __eq__(self, other :object) -> bool:
		if not isinstance(other, LocalPackage):
			return NotImplemented

		return VersionDef(self.version) == VersionDef(other.version)

	def __lt__(self, other :object) -> bool:
		if not isinstance(other, LocalPackage):
			return NotImplemented

		return VersionDef(self.version) < VersionDef(other.version)
