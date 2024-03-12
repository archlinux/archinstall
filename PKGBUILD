# Maintainer: David Runge <dvzrv@archlinux.org>
# Maintainer: Giancarlo Razzolini <grazzolini@archlinux.org>
# Contributor: Anton Hvornum <anton@hvornum.se>
# Contributor: demostanis worlds <demostanis@protonmail.com>

pkgname=archinstall
pkgver=2.7.2
pkgrel=1
pkgdesc="Just another guided/automated Arch Linux installer with a twist"
arch=(any)
url="https://github.com/archlinux/archinstall"
license=(GPL-3.0-or-later)
depends=(
  'arch-install-scripts'
  'coreutils'
  'cryptsetup'
  'e2fsprogs'
  'glibc'
  'kbd'
  'pciutils'
  'procps-ng'
  'python'
  'python-pyparted'
  'python-simple-term-menu'
  'systemd'
  'mkinitcpio'
  'util-linux'
  'base'
  'base-devel'
)
makedepends=(
  'python-setuptools'
  'python-sphinx'
  'python-build'
  'python-installer'
  'python-wheel'
)
optdepends=(
  'linux: Used when linux kernel is selected'
  'linux-lts: Used when linux-lts kernel is selected'
  'linux-zen: Used when linux-zen kernel is selected'
  'linux-hardened: Used when linux-hardened kernel is selected'
  'amd-ucode: Used when AMD microcode dependency is detected'
  'intel-ucode: Used when Intel microcode dependency is detected'
  'btrfs-progs: Used when btrfs is selected as a filesystem'
  'xfsprogs: Used when xfs is selected as a filesystem'
  'f2fs-tools: Used when f2fs is selected as a filesystem'
  'python-systemd: Adds journald logging'
  'xorg-server: Adds the base for X11 based desktop profiles'
  'nano: Used in desktop profile to give simple tooling'
  'vim: Used in desktop profile to give simple tooling'
  'openssh: Used in desktop profile to give simple tooling'
  'htop: Used in desktop profile to give simple tooling'
  'wget: Used in desktop profile to give simple tooling'
  'iwd: Used in desktop profile to give simple tooling'
  'wireless_tools: Used in desktop profile to give simple tooling'
  'wpa_supplicant: Used in desktop profile to give simple tooling'
  'smartmontools: Used in desktop profile to give simple tooling'
  'xdg-utils: Used in desktop profile to give simple tooling'
  'tomcat10: Used in server profile when tomcat is selected'
  'openssh: Used in server profile when sshd is selected'
  'postgresql: Used in server profile when postgresql is selected'
  'nginx: Used in server profile when nginx is selected'
  'mariadb: Used in server profile when mariadb is selected'
  'lighttpd: Used in server profile when lighttpd is selected'
  'apache: Used in server profile when httpd is selected'
  'docker: Used in server profile when docker is selected'
  'cockpit: Used in server profile when cockpit is selected'
  'udisks2: Used in server profile when cockpit is selected'
  'packagekit: Used in server profile when cockpit is selected'
  'alacritty: Used when qtile, awesome desktop is selected'
  'xterm: Used when i3, awesome desktop is selected'
  'slock: Used when lxqt, awesome desktop is selected'
  'brltty: Used if accessibility was detected during installation'
  'espeakup: Used if accessibility was detected during installation'
  'alsa-utils: Used if accessibility was detected during installation'
  'xfce4: Used in server profile when xfce4 is selected'
  'xfce4-goodies: Used in server profile when xfce4 is selected'
  'pavucontrol: Used in server profile when xfce4, sway is selected'
  'gvfs: Used in server profile when xfce4 is selected'
  'xarchiver: Used in server profile when xfce4 is selected'
  'sway: Used when sway desktop is selected'
  'swaybg: Used when sway desktop is selected'
  'swaylock: Used when sway desktop is selected'
  'swayidle: Used when sway desktop is selected'
  'waybar: Used when sway desktop is selected'
  'dmenu: Used when sway desktop is selected'
  'brightnessctl: Used when sway desktop is selected'
  'grim: Used when sway desktop is selected'
  'slurp: Used when sway desktop is selected'
  'foot: Used when sway desktop is selected'
  'xorg-xwayland: Used when sway desktop is selected'
  'seatd: Used when sway desktop is selected with seatd'
  'polkit: Used when sway desktop is selected with polkit'
  'dolphin: Used when kde, hyprland desktop is selected'
  'qtile: Used when qtile desktop is selected'
  'mate: Used when mate desktop is selected'
  'mate-extra: Used when mate desktop is selected'
  'lxqt: Used when lxqt desktop is selected'
  'breeze-icons: Used when lxqt desktop is selected'
  'oxygen-icons: Used when lxqt desktop is selected'
  'ttf-freefont: Used when lxqt desktop is selected'
  'leafpad: Used when lxqt desktop is selected'
  'plasma-meta: Used when kde desktop is selected'
  'konsole: Used when kde desktop is selected'
  'kwrite: Used when kde desktop is selected'
  'ark: Used when kde desktop is selected'
  'plasma-workspace: Used when kde desktop is selected'
  'egl-wayland: Used when kde desktop is selected'
  'i3-wm: Used when i3 desktop is selected'
  'i3lock: Used when i3 desktop is selected'
  'i3status: Used when i3 desktop is selected'
  'i3blocks: Used when i3 desktop is selected'
  'lightdm-gtk-greeter: Used when i3 desktop is selected'
  'lightdm: Used when i3 desktop is selected'
  'dmenu: Used when i3 desktop is selected'
  'hyprland: Used when hyprland desktop is selected'
  'dunst: Used when hyprland desktop is selected'
  'kitty: Used when hyprland desktop is selected'
  'wofi: Used when hyprland desktop is selected'
  'xdg-desktop-portal-hyprland: Used when hyprland desktop is selected'
  'qt5-wayland: Used when hyprland desktop is selected'
  'qt6-wayland: Used when hyprland desktop is selected'
  'gnome: Used when gnome desktop is selected'
  'gnome-tweaks: Used when gnome desktop is selected'
  'enlightenment: Used when enlightenment desktop is selected'
  'terminology: Used when enlightenment desktop is selected'
  'deepin: Used when deepin desktop is selected'
  'deepin-terminal: Used when deepin desktop is selected'
  'deepin-editor: Used when deepin desktop is selected'
  'cutefish: Used when cutefish desktop is selected'
  'noto-fonts: Used when cutefish desktop is selected'
  'cinnamon: Used when cinnamon desktop is slected'
  'system-config-printer: Used when cinnamon desktop is slected'
  'gnome-keyring: Used when cinnamon desktop is slected'
  'gnome-terminal: Used when cinnamon desktop is slected'
  'blueberry: Used when cinnamon desktop is slected'
  'metacity: Used when cinnamon desktop is slected'
  'budgie: Used when budgie desktop is slected'
  'arc-gtk-theme: Used when budgie desktop is slected'
  'mate-terminal: Used when budgie desktop is slected'
  'nemo: Used when budgie desktop is slected'
  'papirus-icon-theme: Used when budgie desktop is slected'
  'bspwm: Used when bspwn desktop is selected'
  'sxhkd: Used when bspwn desktop is selected'
  'dmenu: Used when bspwn desktop is selected'
  'xdo: Used when bspwn desktop is selected'
  'rxvt-unicode: Used when bspwn desktop is selected'
  'awesome: Used when awesome desktop is selected'
  'xorg-xinit: Used when awesome desktop is selected'
  'xorg-xrandr: Used when awesome desktop is selected'
  'feh: Used when awesome desktop is selected'
  'terminus-font: Used when awesome desktop is selected'
  'gnu-free-fonts: Used when awesome desktop is selected'
  'ttf-liberation: Used when awesome desktop is selected'
  'xsel: Used when awesome desktop is selected'
  'pipewire: Used when pipewire is selected as an audio server'
  'pipewire-alsa: Used when pipewire is selected as an audio server'
  'pipewire-jack: Used when pipewire is selected as an audio server'
  'pipewire-pulse: Used when pipewire is selected as an audio server'
  'gst-plugin-pipewire: Used when pipewire is selected as an audio server'
  'libpulse: Used when pipewire is selected as an audio server'
  'wireplumber: Used when pipewire is selected as an audio server'
  'pulseaudio: Used when pulseaudio is selected as an audio server'
  'grub: Used in server profile when grub bootloader option is selected'
  'efibootmgr: Used in server profile when efistub bootloader option is selected'
  'limine: Used in server profile when limine bootloader option is selected'
)
provides=(python-archinstall archinstall)
conflicts=(python-archinstall archinstall-git)
replaces=(python-archinstall archinstall-git)
source=(
  $pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz
  $pkgname-$pkgver.tar.gz.sig::$url/releases/download/v$pkgver/$pkgname-$pkgver.tar.gz.sig
)
sha512sums=('64cb3593c5091b3885ad14ef073cfab31090b4f9bcb4405b18cf9b19adb5ca42255ba8891ec62e21f92d59872541ef6d94f186fb05c625822af63525441e08d9'
            'SKIP')
b2sums=('9c0ec0871841804377ba8310dc744711adcec4eed7319a8d89d684af8e7b822bb9d47540b00f4d746a9fcd7b9ea1b9e07bac773e6c28fabc760e4df38b16748b'
        'SKIP')
validpgpkeys=('256F73CEEFC6705C6BBAB20E5FBBB32941E3740A') # Anton Hvornum (Torxed) <anton@hvornum.se>

pkgver() {
  cd $pkgname-$pkgver

  awk '$1 ~ /^__version__/ {gsub("\"", ""); print $3}' archinstall/__init__.py
}

prepare() {
  cd $pkgname-$pkgver
}

build() {
  cd $pkgname-$pkgver
  python -m build --wheel --no-isolation
  PYTHONDONTWRITEBYTECODE=1 make man -C docs
}

package() {
  cd $pkgname-$pkgver
  python -m installer --destdir="$pkgdir" dist/*.whl
  install -vDm 644 docs/_build/man/archinstall.1 -t "$pkgdir/usr/share/man/man1/"
}

check() {
  cd $pkgname-$pkgver
  # Once we adopt pytest or something similar,
  # this is where the test call will live
}