# Used to do a minimal install

is_top_level_profile = True

__description__ = 'A very basic installation that allows you to customize Arch Linux as you see fit.'


def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. For minimal install,
	we don't need to do anything special here, but it
	needs to exist and return True.
	"""
	return True  # Do nothing and just return True


if __name__ == 'minimal':
	"""
	This "profile" is a meta-profile.
	It is used for a custom minimal installation, without any desktop-specific packages.
	"""
