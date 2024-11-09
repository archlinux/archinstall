# Maintainer: David Runge <dvzrv@archlinux.org>
# Maintainer: Giancarlo Razzolini <grazzolini@archlinux.org>
# Contributor: Anton Hvornum <anton@hvornum.se>
# Contributor: demostanis worlds <demostanis@protonmail.com>

pkgname=archinstall
pkgver=2.6.0
pkgrel=1
pkgdesc="Just another guided/automated Arch Linux installer with a twist"
arch=(any)
url="https://github.com/archlinux/archinstall"
license=(GPL3)
depends=(
  'arch-install-scripts'
  'btrfs-progs'
  'coreutils'
  'cryptsetup'
  'dosfstools'
  'e2fsprogs'
  'glibc'
  'kbd'
  'pciutils'
  'procps-ng'
  'python'
  'python-pydantic'
  'python-pyparted'
  'python-simple-term-menu'
  'systemd'
  'util-linux'
  'xfsprogs'
  'lvm2'
  'f2fs-tools'
  'ntfs-3g'
  'reiserfsprogs'
)
makedepends=(
  'python-setuptools'
  'python-sphinx'
  'python-build'
  'python-installer'
  'python-wheel'
)
optdepends=(
  'python-systemd: Adds journald logging'
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

  # use real directories for examples and profiles, as symlinks do not work
  rm -fv $pkgname/{examples,profiles}
}

build() {
  cd $pkgname-$pkgver

  python -m build --wheel --no-isolation
  PYTHONDONTWRITEBYTECODE=1 make man -C docs
}

package() {
  cd "$pkgname-$pkgver"

  python -m installer --destdir="$pkgdir" dist/*.whl
  install -vDm 644 docs/_build/man/archinstall.1 -t "$pkgdir/usr/share/man/man1/"
}
