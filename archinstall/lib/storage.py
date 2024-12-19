# There's a few scenarios of execution:
#   1. In the git repository, where ./profiles_bck/ exist
#   2. When executing from a remote directory, but targeted a script that starts from the git repository
#   3. When executing as a python -m archinstall module where profiles_bck exist one step back for library reasons.
#   (4. Added the ~/.config directory as an additional option for future reasons)
#
# And Keeping this in dict ensures that variables are shared across imports.
from pathlib import Path
from typing import Any

storage: dict[str, Any] = {
	'PROFILE': Path(__file__).parent.parent.joinpath('default_profiles'),
	'LOG_PATH': Path('/var/log/archinstall'),
	'LOG_FILE': Path('install.log'),
	'MOUNT_POINT': Path('/mnt/archinstall'),
	'ENC_IDENTIFIER': 'ainst',
	'CMD_LOCALE': {'LC_ALL': 'C'},  # default locale for execution commands. Can be overridden with set_cmd_locale()
	'CMD_LOCALE_DEFAULT': {'LC_ALL': 'C'},  # should be the same as the former. Not be used except in reset_cmd_locale()
}
