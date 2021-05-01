import archinstall

# Define the package list in order for lib to source
# which packages will be installed by this profile
__packages__ = ["mariadb"]

installation.add_additional_packages(__packages__)

installation.arch_chroot("mariadb-install-db --user=mysql --basedir=/usr --datadir=/var/lib/mysql")

installation.enable_service('mariadb')
