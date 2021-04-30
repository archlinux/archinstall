import archinstall

# Define the package list in order for lib to source
# which packages will be installed by this profile
__packages__ = ["apparmor"]


def on_bootloader(instance):
	instance.KERNEL_PARAMS.insert(0, "lsm=lockdown,yama,apparmor,bpf")


installation.add_additional_packages(__packages__)

installation.enable_service("apparmor")
