import os

# There's a few scenarios of execution:
#   1. In the git repository, where ./profiles/ exist
#   2. When executing from a remote directory, but targeted a script that starts from the git repository
#   3. When executing as a python -m archinstall module where profiles exist one step back for library reasons.
#   (4. Added the ~/.config directory as an additional option for future reasons)
#
# And Keeping this in dict ensures that variables are shared across imports.
storage = {
	'PROFILE_PATH': [
		'./profiles',
		'~/.config/archinstall/profiles',
		os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'profiles'),
		# os.path.abspath(f'{os.path.dirname(__file__)}/../examples')
	],
	'UPSTREAM_URL': 'https://raw.githubusercontent.com/archlinux/archinstall/master/profiles',
	'PROFILE_DB': None,  # Used in cases when listing profiles is desired, not mandatory for direct profile grabing.
	'LOG_PATH': '/var/log/archinstall',
	'LOG_FILE': 'install.log',
	'MOUNT_POINT': '/mnt/archinstall',
	'ENC_IDENTIFIER': 'ainst',
	'DISK_TIMEOUTS' : 1, # seconds
	'DISK_RETRY_ATTEMPTS' : 20, # RETRY_ATTEMPTS * DISK_TIMEOUTS is used in disk operations
}
