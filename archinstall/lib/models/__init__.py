from typing import Optional, List
from pydantic import BaseModel, validator

class VersionDef(BaseModel):
	version_string: str

	@classmethod
	def parse_version(cls) -> List[str]:
		if '.' in version_string:
			versions = version_string.split('.')
		else:
			versions = [version_string]

		return versions

	@classmethod
	def major(self) -> str:
		return self.parse_version()[0]

	@classmethod
	def minor(self) -> str:
		versions = self.parse_version()
		if len(versions) >= 2:
			return versions[1]

	@classmethod
	def patch(self) -> str:
		versions = self.parse_version()
		if '-' in versions[-1]:
			_, patch_version = versions[-1].split('-', 1)
			return patch_version

	def __eq__(self, other :'VersionDef') -> bool:
		if other.major == self.major and \
			other.minor == self.minor and \
			other.patch == self.patch:

			return True
		return False
		
	def __lt__(self, other :'VersionDef') -> bool:
		if self.major > other.major:
			return False
		elif self.minor and other.minor and self.minor > other.minor:
			return False
		elif self.patch and other.patch and self.patch > other.patch:
			return False

	def __str__(self) -> str:
		return self.version_string


class PackageSearchResult(BaseModel):
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

	def __eq__(self, other :'VersionDef') -> bool:
		return self.pkg_version == other.pkg_version

	def __lt__(self, other :'VersionDef') -> bool:
		return self.pkg_version < other.pkg_version


class PackageSearch(BaseModel):
	version: int
	limit: int
	valid: bool
	results: List[PackageSearchResult]


class LocalPackage(BaseModel):
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

	@property
	def pkg_version(self) -> str:
		return self.version

	def __eq__(self, other :'VersionDef') -> bool:
		return self.pkg_version == other.pkg_version

	def __lt__(self, other :'VersionDef') -> bool:
		return self.pkg_version < other.pkg_version