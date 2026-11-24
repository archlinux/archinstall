import asyncio

import pytest

from archinstall.default_profiles.desktops.plasma import PlasmaProfile
from archinstall.default_profiles.profile import Profile
from archinstall.lib.hardware import GfxDriver
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.profile import profile_menu


async def _return_preset(preset: Profile | None) -> Profile | None:
	return preset


def test_reopening_profile_type_keeps_selected_gfx_driver(monkeypatch: pytest.MonkeyPatch) -> None:
	profile = PlasmaProfile()
	menu = profile_menu.ProfileMenu(ProfileConfiguration(profile=profile, gfx_driver=GfxDriver.NvidiaOpenKernel))
	monkeypatch.setattr(profile_menu, 'select_profile', _return_preset)

	asyncio.run(menu._select_profile(profile))

	assert menu._item_group.find_by_key('gfx_driver').value == GfxDriver.NvidiaOpenKernel


def test_selecting_graphical_profile_defaults_gfx_driver_to_open_source(monkeypatch: pytest.MonkeyPatch) -> None:
	profile = PlasmaProfile()
	menu = profile_menu.ProfileMenu()
	monkeypatch.setattr(profile_menu, 'select_profile', _return_preset)

	asyncio.run(menu._select_profile(profile))

	assert menu._item_group.find_by_key('gfx_driver').value == GfxDriver.AllOpenSource
