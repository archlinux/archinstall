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
	"LOG_PATH": Path("/var/log/archinstall"),
	"LOG_FILE": Path("install.log"),
}
