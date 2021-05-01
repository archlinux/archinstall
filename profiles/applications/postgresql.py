import archinstall

# Define the package list in order for lib to source
# which packages will be installed by this profile
__packages__ = ["postgresql"]

installation.add_additional_packages(__packages__)

installation.arch_chroot("initdb -D /var/lib/postgres/data", runas='postgres')

installation.enable_service('postgresql')