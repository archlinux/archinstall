import pytest

from archinstall.default_profiles.desktops.gnome import GnomeProfile
from archinstall.default_profiles.desktops.plasma import PlasmaProfile
from archinstall.default_profiles.desktops.xfce4 import Xfce4Profile
from archinstall.default_profiles.desktops.mate import MateProfile
from archinstall.default_profiles.desktops.cinnamon import CinnamonProfile
from archinstall.default_profiles.desktops.budgie import BudgieProfile
from archinstall.default_profiles.desktops.deepin import DeepinProfile
from archinstall.default_profiles.desktops.lxqt import LxqtProfile

# List of desktop profiles to test
desktop_profiles = [
    GnomeProfile,
    PlasmaProfile,
    Xfce4Profile,
    MateProfile,
    CinnamonProfile,
    BudgieProfile,
    DeepinProfile,
    LxqtProfile,
]

@pytest.mark.parametrize("profile_class", desktop_profiles)
def test_orca_included_when_accessibility_enabled(profile_class):
    profile = profile_class()
    profile.accessibility = True
    assert "orca" in profile.packages

@pytest.mark.parametrize("profile_class", desktop_profiles)
def test_orca_not_included_when_accessibility_disabled(profile_class):
    profile = profile_class()
    profile.accessibility = False
    assert "orca" not in profile.packages
