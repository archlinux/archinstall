FROM l4zy/archlinux:latest
VOLUME [ “/sys/fs/cgroup” ]
VOLUME [ “/sys/fs/fuse” ]
RUN pacman -Syy archinstall parted dosfstools btrfs-progs arch-install-scripts --noconfirm
