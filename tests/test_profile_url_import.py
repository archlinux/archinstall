from pytest import MonkeyPatch

from archinstall.lib.profile.profiles_handler import ProfileHandler, ProfileSerialization


def test_parse_profile_config_imports_profile_from_url(monkeypatch: MonkeyPatch) -> None:
	custom_profile_code = b"""
from archinstall.default_profiles.profile import Profile, ProfileType

class CustomUrlProfile(Profile):
	def __init__(self) -> None:
		super().__init__('CustomUrlProfile', ProfileType.CustomType)
"""

	monkeypatch.setattr(
		'archinstall.lib.profile.profiles_handler.fetch_data_from_url',
		lambda _url: custom_profile_code,
	)

	handler = ProfileHandler()
	profile_config: ProfileSerialization = {
		'path': 'https://example.com/custom_profile.py',
		'main': 'CustomUrlProfile',
	}

	profile = handler.parse_profile_config(profile_config)

	assert profile is not None
	assert profile.name == 'CustomUrlProfile'
