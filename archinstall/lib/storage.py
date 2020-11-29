storage = {}

PROFILE_PATH = ['./profiles', '~/.config/archinstall/profiles', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'profiles')]
UPSTREAM_URL = 'https://raw.githubusercontent.com/Torxed/archinstall/master/profiles'
PROFILE_DB = None # Used in cases when listing profiles is desired, not mandatory for direct profile grabing.