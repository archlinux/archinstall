import archinstall

# "It is recommended also to install the gnome group, which contains applications required for the standard GNOME experience." - Arch Wiki 
__packages__ = ["budgie-desktop", "lightdm", "lightdm-gtk-greeter", "gnome"]

installation.add_additional_packages(__packages__)
