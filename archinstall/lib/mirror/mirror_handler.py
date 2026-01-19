import time
import urllib.parse
from pathlib import Path

from ..models.mirrors import (
	MirrorRegion,
	MirrorStatusEntryV3,
	MirrorStatusListV3,
)
from ..networking import fetch_data_from_url
from ..output import debug, info


class MirrorListHandler:
	def __init__(
		self,
		local_mirrorlist: Path = Path('/etc/pacman.d/mirrorlist'),
	) -> None:
		self._local_mirrorlist = local_mirrorlist
		self._status_mappings: dict[str, list[MirrorStatusEntryV3]] | None = None
		self._fetched_remote: bool = False

	def _mappings(self) -> dict[str, list[MirrorStatusEntryV3]]:
		if self._status_mappings is None:
			self.load_mirrors()

		assert self._status_mappings is not None
		return self._status_mappings

	def get_mirror_regions(self) -> list[MirrorRegion]:
		available_mirrors = []
		mappings = self._mappings()

		for region_name, status_entry in mappings.items():
			urls = [entry.server_url for entry in status_entry]
			region = MirrorRegion(region_name, urls)
			available_mirrors.append(region)

		return available_mirrors

	def load_mirrors(self) -> None:
		from .args import arch_config_handler

		if arch_config_handler.args.offline:
			self._fetched_remote = False
			self.load_local_mirrors()
		else:
			self._fetched_remote = self.load_remote_mirrors()
			debug(f'load mirrors: {self._fetched_remote}')
			if not self._fetched_remote:
				self.load_local_mirrors()

	def load_remote_mirrors(self) -> bool:
		url = 'https://archlinux.org/mirrors/status/json/'
		attempts = 3

		for attempt_nr in range(attempts):
			try:
				mirrorlist = fetch_data_from_url(url)
				self._status_mappings = self._parse_remote_mirror_list(mirrorlist)
				return True
			except Exception as e:
				debug(f'Error while fetching mirror list: {e}')
				time.sleep(attempt_nr + 1)

		debug('Unable to fetch mirror list remotely, falling back to local mirror list')
		return False

	def load_local_mirrors(self) -> None:
		with self._local_mirrorlist.open('r') as fp:
			mirrorlist = fp.read()
			self._status_mappings = self._parse_locale_mirrors(mirrorlist)

	def get_status_by_region(self, region: str, speed_sort: bool) -> list[MirrorStatusEntryV3]:
		mappings = self._mappings()
		region_list = mappings[region]

		# Only sort if we have remote mirror data with score/speed info
		# Local mirrors lack this data and can be modified manually before-hand
		# Or reflector potentially ran already
		if self._fetched_remote and speed_sort:
			info('Sorting your selected mirror list based on the speed between you and the individual mirrors (this might take a while)')
			# Sort by speed descending (higher is better in bitrate form core.db download)
			return sorted(region_list, key=lambda mirror: -mirror.speed)
		# just return as-is without sorting?
		return region_list

	def _parse_remote_mirror_list(self, mirrorlist: str) -> dict[str, list[MirrorStatusEntryV3]]:
		mirror_status = MirrorStatusListV3.model_validate_json(mirrorlist)

		sorting_placeholder: dict[str, list[MirrorStatusEntryV3]] = {}

		for mirror in mirror_status.urls:
			# We filter out mirrors that have bad criteria values
			if any(
				[
					mirror.active is False,  # Disabled by mirror-list admins
					mirror.last_sync is None,  # Has not synced recently
					# mirror.score (error rate) over time reported from backend:
					# https://github.com/archlinux/archweb/blob/31333d3516c91db9a2f2d12260bd61656c011fd1/mirrors/utils.py#L111C22-L111C66
					(mirror.score is None or mirror.score >= 100),
				]
			):
				continue

			if mirror.country == '':
				# TODO: This should be removed once RFC!29 is merged and completed
				# Until then, there are mirrors which lacks data in the backend
				# and there is no way of knowing where they're located.
				# So we have to assume world-wide
				mirror.country = 'Worldwide'

			if mirror.url.startswith('http'):
				sorting_placeholder.setdefault(mirror.country, []).append(mirror)

		sorted_by_regions: dict[str, list[MirrorStatusEntryV3]] = dict(
			{region: unsorted_mirrors for region, unsorted_mirrors in sorted(sorting_placeholder.items(), key=lambda item: item[0])}
		)

		return sorted_by_regions

	def _parse_locale_mirrors(self, mirrorlist: str) -> dict[str, list[MirrorStatusEntryV3]]:
		lines = mirrorlist.splitlines()

		# remove empty lines
		# lines = [line for line in lines if line]

		mirror_list: dict[str, list[MirrorStatusEntryV3]] = {}

		current_region = ''

		for line in lines:
			line = line.strip()

			if line.startswith('## '):
				current_region = line.replace('## ', '').strip()
				mirror_list.setdefault(current_region, [])

			if line.startswith('Server = '):
				if not current_region:
					current_region = 'Local'
					mirror_list.setdefault(current_region, [])

				url = line.removeprefix('Server = ')

				mirror_entry = MirrorStatusEntryV3(
					url=url.removesuffix('$repo/os/$arch'),
					protocol=urllib.parse.urlparse(url).scheme,
					active=True,
					country=current_region or 'Worldwide',
					# The following values are normally populated by
					# archlinux.org mirror-list endpoint, and can't be known
					# from just the local mirror-list file.
					country_code='WW',
					isos=True,
					ipv4=True,
					ipv6=True,
					details='Locally defined mirror',
				)

				mirror_list[current_region].append(mirror_entry)

		return mirror_list


mirror_list_handler = MirrorListHandler()
