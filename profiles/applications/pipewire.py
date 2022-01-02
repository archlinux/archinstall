import archinstall

# Define the package list in order for lib to source
# which packages will be installed by this profile
__packages__ = ["pipewire", "pipewire-alsa", "pipewire-jack", "pipewire-media-session", "pipewire-pulse", "gst-plugin-pipewire", "libpulse"]

print('Installing pipewire ...')
print(archinstall.storage)
archinstall.storage['installation_session'].add_additional_packages(__packages__)

@archinstall.plugin
def on_user_created(installation :archinstall.Installer, user :str):
	installation.chroot('systemctl enable --user pipewire-pulse.service', run_as=user)