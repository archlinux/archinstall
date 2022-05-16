import typing
import pathlib
from ..general import SysCommand

def udevadm_info(path :pathlib.Path) -> typing.Dict[str, str]:
	if path.resolve().exists() is False:
		return {}

	result = SysCommand(f"udevadm info {path.resolve()}")
	data = {}
	for line in result:
		if b': ' in line and b'=' in line:
			_, obj = line.split(b': ', 1)
			key, value = obj.split(b'=', 1)
			data[key.decode('UTF-8').lower()] = value.decode('UTF-8').strip()

	return data