from .lib.general import *
from .lib.disk import *
from .lib.user_interaction import *
from .lib.exceptions import *
from .lib.installer import *
from .lib.profiles import *
from .lib.luks import *
from .lib.mirrors import *
from .lib.networking import *
from .lib.locale_helpers import *
from .lib.services import *
from .lib.packages import *
from .lib.output import *
from .lib.storage import *
from .lib.hardware import *

## Basic version of arg.parse() supporting:
##  --key=value
##  --boolean
arguments = {}
positionals = []
for arg in sys.argv[1:]:
	if '--' == arg[:2]:
		if '=' in arg:
			key, val = [x.strip() for x in arg[2:].split('=', 1)]
		else:
			key, val = arg[2:], True
		arguments[key] = val
	else:
		positionals.append(arg)