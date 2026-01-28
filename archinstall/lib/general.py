import json
from datetime import date, datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, override

from archinstall.lib.packages.packages import check_package_upgrade

from .output import debug


@lru_cache(maxsize=128)
def check_version_upgrade() -> str | None:
	debug('Checking version')
	upgrade = None

	upgrade = check_package_upgrade('archinstall')

	if upgrade is None:
		debug('No archinstall upgrades found')
		return None

	debug(f'Archinstall latest: {upgrade}')

	return upgrade


def running_from_host() -> bool:
	"""
	Check if running from an installed system.

	Returns True if running from installed system (host mode) for host-to-target install.
	Returns False if /run/archiso exists (ISO mode).
	"""
	is_host = not Path('/run/archiso').exists()
	return is_host


def jsonify(obj: Any, safe: bool = True) -> Any:
	"""
	Converts objects into json.dumps() compatible nested dictionaries.
	Setting safe to True skips dictionary keys starting with a bang (!)
	"""

	compatible_types = str, int, float, bool
	if isinstance(obj, dict):
		return {
			key: jsonify(value, safe)
			for key, value in obj.items()
			if isinstance(key, compatible_types) and not (isinstance(key, str) and key.startswith('!') and safe)
		}
	if isinstance(obj, Enum):
		return obj.value
	if hasattr(obj, 'json'):
		# json() is a friendly name for json-helper, it should return
		# a dictionary representation of the object so that it can be
		# processed by the json library.
		return jsonify(obj.json(), safe)
	if isinstance(obj, datetime | date):
		return obj.isoformat()
	if isinstance(obj, list | set | tuple):
		return [jsonify(item, safe) for item in obj]
	if isinstance(obj, Path):
		return str(obj)
	if hasattr(obj, '__dict__'):
		return vars(obj)

	return obj


class JSON(json.JSONEncoder, json.JSONDecoder):
	"""
	A safe JSON encoder that will omit private information in dicts (starting with !)
	"""

	@override
	def encode(self, o: Any) -> str:
		return super().encode(jsonify(o))


class UNSAFE_JSON(json.JSONEncoder, json.JSONDecoder):
	"""
	UNSAFE_JSON will call/encode and keep private information in dicts (starting with !)
	"""

	@override
	def encode(self, o: Any) -> str:
		return super().encode(jsonify(o, safe=False))
