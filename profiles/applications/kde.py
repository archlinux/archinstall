import archinstall

# Other packages for KDE are installed in the main profile now.

if "nvidia" in _gfx_driver_packages:
	installation.add_additional_packages("egl-wayland")
