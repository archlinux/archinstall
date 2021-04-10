import archinstall

# "It is recommended also to install the gnome group, which contains applications required for the standard GNOME experience." - Arch Wiki 
installation.add_additional_packages("budgie-desktop lightdm lightdm-gtk-greeter gnome")