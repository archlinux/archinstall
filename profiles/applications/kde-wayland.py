import archinstall
packages = "plasma-meta kde-applications-meta plasma-wayland-session sddm"
# if the package selection can be reduced go for it
if "nvidia" in _gfx_driver_packages:
	packages = packages + " egl-wayland"
installation.add_additional_packages(packages)
# We'll support plasma-desktop-wayland (minimal) later
