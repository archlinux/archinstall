from pathlib import Path

import pytest

from archinstall.lib.locale import utils


def test_list_timezones_reads_zone_tab_without_backward_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	zone_tab = tmp_path / 'zone.tab'
	zone_tab.write_text(
		'# tzdata comment\nUA\t+5026+03031\tEurope/Kyiv\tmost of Ukraine\nNL\t+5222+00454\tEurope/Amsterdam\n',
	)
	monkeypatch.setattr(utils, 'ZONE_TAB', zone_tab)

	timezones = utils.list_timezones()

	assert timezones == ['Europe/Amsterdam', 'Europe/Kyiv', 'UTC']
