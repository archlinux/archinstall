import asyncio
from collections.abc import Callable

import pytest

from archinstall.default_profiles.desktops.hyprland import HyprlandProfile
from archinstall.default_profiles.desktops.labwc import LabwcProfile
from archinstall.default_profiles.desktops.niri import NiriProfile
from archinstall.default_profiles.desktops.sway import SwayProfile
from archinstall.default_profiles.desktops.utils import SeatAccess
from archinstall.default_profiles.profile import CustomSetting, Profile
from archinstall.lib.menu.helpers import Selection
from archinstall.tui.result import Result


@pytest.mark.parametrize('profile_type', [HyprlandProfile, LabwcProfile, NiriProfile, SwayProfile])
@pytest.mark.parametrize('default', [None, 'seatd', 'polkit'])
@pytest.mark.parametrize('choice', [None, 'seatd', 'polkit'])
def test_seat_access_selection(
	monkeypatch: pytest.MonkeyPatch,
	profile_type: Callable[[], Profile],
	default: str | None,
	choice: str | None,
) -> None:
	async def show(selection: Selection[SeatAccess]) -> Result[SeatAccess]:
		group = selection._group
		assert [(item.text, item.get_value().value) for item in group.items] == [
			('seatd', 'seatd'),
			('systemd-logind', 'polkit'),
		]
		index = group.get_focused_index()
		assert index == (0 if default == 'seatd' else 1)
		if choice is None:
			return Result[SeatAccess].selection(group.get_enabled_items()[index].get_value())
		return Result[SeatAccess].selection(next(item.get_value() for item in group.items if item.get_value().value == choice))

	monkeypatch.setattr(Selection, 'show', show)
	profile = profile_type()
	profile.custom_settings[CustomSetting.SeatAccess] = default
	asyncio.run(profile.do_on_select())
	assert profile.custom_settings[CustomSetting.SeatAccess] == (choice or default or 'polkit')


@pytest.mark.parametrize('profile_type', [HyprlandProfile, LabwcProfile, NiriProfile, SwayProfile])
@pytest.mark.parametrize(('setting', 'services'), [(None, []), ('seatd', ['seatd']), ('polkit', [])])
def test_seat_access_services(profile_type: Callable[[], Profile], setting: str | None, services: list[str]) -> None:
	profile = profile_type()
	profile.custom_settings[CustomSetting.SeatAccess] = setting
	assert profile.services == services
