# Maintainer: David Runge <dvzrv@archlinux.org>
# Maintainer: Giancarlo Razzolini <grazzolini@archlinux.org>
# Contributor: Anton Hvornum <anton@hvornum.se>
# Contributor: demostanis worlds <demostanis@protonmail.com>

pkgname=archinstall
pkgver=2.5.0
#pkgver=$(git describe --long | sed 's/\([^-]*-g\)/r\1/;s/-/./g')
pkgrel=1
pkgdesc="Just another guided/automated Arch Linux installer with a twist"
arch=(any)
url="https://github.com/archlinux/archinstall"
license=(GPL3)
depends=(python)
makedepends=(python-build python-installer python-flit python-setuptools python-sphinx python-wheel)
provides=(python-archinstall)
conflicts=(python-archinstall)
replaces=(python-archinstall)
source=(
  $pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz
  $pkgname-$pkgver.tar.gz.sig::$url/releases/download/v$pkgver/$pkgname-$pkgver.tar.gz.sig
)
sha512sums=('9516719c4e4fe0423224a35b4846cf5c8daeb931cff6fed588957840edc5774e9c6fe18619d2356a6d76681ae3216ba19f5d0f0bd89c6301b4ff9b128d037d13'
            'SKIP')
b2sums=('a29ae767756f74ce296d53e31bb8376cfa7db19a53b8c3997b2d8747a60842ba88e8b18c505bc56a36d685f73f7a6d9e53adff17953c8a4ebaabc67c6db8e583'
        'SKIP')
validpgpkeys=('256F73CEEFC6705C6BBAB20E5FBBB32941E3740A') # Anton Hvornum (Torxed) <anton@hvornum.se>

prepare() {
  cd $pkgname-$pkgver
  # use real directories for examples and profiles, as symlinks do not work
  # with flit or setuptools PEP517 backends
  rm -fv $pkgname/{examples,profiles}
  mv -v examples profiles $pkgname/
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