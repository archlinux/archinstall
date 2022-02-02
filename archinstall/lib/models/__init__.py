from typing import Optional, List
from pydantic import BaseModel, validator

class VersionDef(BaseModel):
	major: float
	minor: Optional[float] = None
	patch: Optional[str] = None

	@validator('major', pre=True)
	def construct(cls, value):
		setattr(self, 'version_raw', version_string)
		setattr(self, 'major', version_string)

	def __init__(self, version_string :str):
		setattr(self, 'version_raw', version_string)

		if '.' in version_string:
			self.versions = version_string.split('.')
		else:
			self.versions = [version_string]

		if '-' in self.versions[-1]:
			version, patch_version = self.versions[-1].split('-', 1)
			self.verions = self.versions[:-1] + [version]
			self.patch = patch_version

		self.major = self.versions[0]
		if len(self.versions) >= 2:
			self.minor = self.versions[1]
		if len(self.versions) >= 3:
			self.patch = self.versions[2]

	def __eq__(self, other :'VersionDef') -> bool:
		if other.major == self.major and \
			other.minor == self.minor and \
			other.patch == self.patch:

			return True
		return False
		
	def __lt__(self, other :'VersionDef') -> bool:
		print(f"Comparing {self} against {other}")
		if self.major > other.major:
			return False
		elif self.minor and other.minor and self.minor > other.minor:
			return False
		elif self.patch and other.patch and self.patch > other.patch:
			return False

	def __str__(self) -> str:
		return self.version_raw


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

	@validator('pkgver')
	def pkg_version(cls, pkgver):
		return VersionDef(pkgver)


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

	@validator('version')
	def pkg_version(cls, version):
		return VersionDef(version)