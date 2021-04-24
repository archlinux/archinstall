FROM l4zy/archlinux:latest
RUN pacman -Syy archinstall parted dosfstools btrfs-progs arch-install-scripts --noconfirm
