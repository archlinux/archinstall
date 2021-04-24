FROM archlinux:base-devel-20210131.0.14634
RUN pacman -Syy archinstall parted glibc dosfstools btrfs-progs --noconfirm
