import archinstall
import logging

# Define the package list in order for lib to source
# which packages will be installed by this profile
__packages__ = ["pipewire", "pipewire-alsa", "pipewire-jack", "pipewire-pulse", "gst-plugin-pipewire", "libpulse", "wireplumber"]

archinstall.log('Installing pipewire', level=logging.INFO)
archinstall.storage['installation_session'].add_additional_packages(__packages__)

@archinstall.plugin
def on_user_created(installation :archinstall.Installer, user :str):
	archinstall.log(f"Enabling pipewire-pulse for {user}", level=logging.INFO)
	installation.chroot('systemctl enable --user pipewire-pulse.service', run_as=user)
