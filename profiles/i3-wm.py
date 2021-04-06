import archinstall, subprocess

def _prep_function(*args, **kwargs):
	"""
	Magic function called by the importing installer
	before continuing any further. It also avoids executing any
	other code in this stage. So it's a safe way to ask the user
	for more input before any other installer steps start.
	"""

	# i3 requires a functioning Xorg installation.
	profile = archinstall.Profile(None, 'xorg')
	with profile.load_instructions(namespace='xorg.py') as imported:
		if hasattr(imported, '_prep_function'):
			return imported._prep_function()
		else:
			print('Deprecated (??): xorg profile has no _prep_function() anymore')
def _post_install(*args, **kwargs):
	"""
	Another magic function called after the system 
	has been installed. 
	"""
	print("the installation of i3-gaps does not conatain any configuerations for the wm. in this shell you should take your time to add your configuerations")			
	subprocess.check_call("arch-chroot /mnt",shell=True)

if __name__ == 'i3-wm':
    # Install dependency profiles
    installation.install_profile('xorg')
    # we are installing lightdm to auto start i3
    installation.add_additional_packages("lightdm-gtk-greeter lightdm")
    # install the i3 group now
    i3 = archinstall.Application(installation, 'i3-wm')
    i3.install()
    # Auto start lightdm for all users
    installation.enable_service('lightdm')