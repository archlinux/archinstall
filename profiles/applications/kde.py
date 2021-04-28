import archinstall

packages = "" # Other packages for KDE are installed in the main profile now.

if "nvidia" in _gfx_driver_packages:
	packages = packages + " egl-wayland"

installation.add_additional_packages(packages)
