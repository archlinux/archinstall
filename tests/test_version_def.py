from archinstall.lib.models.dataclasses import VersionDef

def test_version_def_equality() -> None:
	version_a = VersionDef("1.0")
	version_b = VersionDef("1.0")

	assert version_a == version_b

def test_version_def_greater_than_major() -> None:
	version_a = VersionDef("2.0")
	version_b = VersionDef("1.0")

	assert version_a > version_b

def test_version_def_greater_than_minor() -> None:
	version_a = VersionDef("1.1")
	version_b = VersionDef("1.0")

	assert version_a > version_b

def test_version_def_less_than_major() -> None:
	version_a = VersionDef("1.0")
	version_b = VersionDef("2.0")

	assert version_a < version_b

def test_version_def_less_than_minor() -> None:
	version_a = VersionDef("1.0")
	version_b = VersionDef("1.1")

	assert version_a < version_b

def test_version_def_patch() -> None:
	version = VersionDef("1.0-35")

	assert version.patch() == "35"
