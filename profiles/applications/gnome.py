import archinstall

installation.add_additional_packages("gnome gnome-extra gdm") # We'll create a gnome-minimal later, but for now, we'll avoid issues by giving more than we need.
# Note: gdm should be part of the gnome group, but adding it here for clarity