from dataclasses import dataclass
from typing import Optional, List, Any

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

	def __eq__(self, other :'VersionDef') -> bool:
		return self.pkg_version == other.pkg_version

	def __lt__(self, other :'VersionDef') -> bool:
		return self.pkg_version < other.pkg_version

	def __get__(self, key :str) -> Any:
		print('----------------- KEEEE:', key)

@dataclass
class PackageSearch:
	version: int
	limit: int
	valid: bool
	num_pages: int
	page: int
	results: List[PackageSearchResult]

	def __post_init__(self):
		self.results = [PackageSearchResult(**x) for x in self.results]

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

	def __eq__(self, other :'VersionDef') -> bool:
		return self.pkg_version == other.pkg_version

	def __lt__(self, other :'VersionDef') -> bool:
		return self.pkg_version < other.pkg_version