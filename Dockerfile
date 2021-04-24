FROM l4zy/archlinux:latest
ENV container docker
STOPSIGNAL SIGRTMIN+3
RUN pacman -Syy glibc systemd --noconfirm
VOLUME [ “/sys/fs/cgroup” ]
VOLUME [ “/sys/fs/fuse” ]
RUN pacman -Syy archinstall parted dosfstools btrfs-progs arch-install-scripts --noconfirm
