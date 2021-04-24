FROM l4zy/archlinux:latest
ENV container docker
STOPSIGNAL SIGRTMIN+3
RUN pacman -Syy archinstall parted dosfstools btrfs-progs arch-install-scripts --noconfirm
