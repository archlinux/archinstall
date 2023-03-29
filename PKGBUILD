# Maintainer: David Runge <dvzrv@archlinux.org>
# Maintainer: Giancarlo Razzolini <grazzolini@archlinux.org>
# Contributor: Anton Hvornum <anton@hvornum.se>
# Contributor: demostanis worlds <demostanis@protonmail.com>

pkgname=archinstall
#pkgver=2.5.4
pkgrel=1
pkgdesc="Just another guided/automated Arch Linux installer with a twist"
arch=(any)
url="https://github.com/archlinux/archinstall"
license=(GPL3)
depends=(python systemd)
makedepends=(python-build python-installer python-setuptools python-sphinx python-wheel)
provides=(python-archinstall)
conflicts=(python-archinstall)
replaces=(python-archinstall)
source=(
  $pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz
  $pkgname-$pkgver.tar.gz.sig::$url/releases/download/v$pkgver/$pkgname-$pkgver.tar.gz.sig
)
sha512sums=('3bfdd2b33ef3a784bd6c847afce75b0d5c1997f8374db5f75adc6fe9e35ab135e7cdb2fdcef01999fcb6c03ed80159f02d3da560d28e8da8fe17043f4cdac108'
            'SKIP')
b2sums=('87c3ad807e87d834d59210cb28d14c93acabe8996bcc7407866307f9cdddf4e233a35c96e99e02aebbbb95548bdfa125772fb4703bf0152227e4163cd621860a'
        'SKIP')
validpgpkeys=('256F73CEEFC6705C6BBAB20E5FBBB32941E3740A') # Anton Hvornum (Torxed) <anton@hvornum.se>

pkgver() {
  cd $pkgname-$pkgver
  git describe --long --abbrev=7 | sed 's/^v//;s/\([^-]*-g\)/r\1/;s/-/./g' | grep -o -E '[0-9.]{5}'
}

prepare() {
  cd $pkgname-$pkgver
  # use real directories for examples and profiles, as symlinks do not work
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
