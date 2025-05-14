# Maintainer: David Runge <dvzrv@archlinux.org>
# Maintainer: Giancarlo Razzolini <grazzolini@archlinux.org>
# Contributor: Anton Hvornum <anton@hvornum.se>
# Contributor: demostanis worlds <demostanis@protonmail.com>

pkgname=archinstall
pkgver=3.0.5
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
  'libcrypt.so'
  'libxcrypt'
  'pciutils'
  'procps-ng'
  'python'
  'python-pydantic'
  'python-pyparted'
  'systemd'
  'util-linux'
  'xfsprogs'
  'lvm2'
  'f2fs-tools'
  'ntfs-3g'
)
makedepends=(
  'python-cryptography'
  'python-setuptools'
  'python-sphinx'
  'python-build'
  'python-installer'
  'python-wheel'
  'python-sphinx_rtd_theme'
)
optdepends=(
  'python-systemd: Adds journald logging'
)
provides=(python-archinstall archinstall)
conflicts=(python-archinstall archinstall-git)
replaces=(python-archinstall archinstall-git)
source=(
  $pkgname-$pkgver.tar.gz::$url/archive/refs/tags/$pkgver.tar.gz
  $pkgname-$pkgver.tar.gz.sig::$url/releases/download/$pkgver/$pkgname-$pkgver.tar.gz.sig
)
sha512sums=()
b2sums=()
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
