# Maintainer: Anton Hvornum <anton@hvornum.se>
# Contributor: Giancarlo Razzolini <grazzolini@archlinux.org>
# Contributor: demostanis worlds <demostanis@protonmail.com>

pkgname=archinstall-git
pkgver=$(git describe --long | sed 's/\([^-]*-g\)/r\1/;s/-/./g')
pkgrel=1
pkgdesc="Just another guided/automated Arch Linux installer with a twist"
arch=('any')
url="https://github.com/archlinux/archinstall"
license=('GPL')
depends=('python')
makedepends=('python-setuptools' 'python-sphinx')
provides=('python-archinstall')
conflicts=('archinstall' 'python-archinstall' 'python-archinstall-git')

build() {
        cd "$startdir"
        python setup.py build
        make man -C docs
}

package() {
        cd "$startdir"
        python setup.py install --root="${pkgdir}" --optimize=1 --skip-build
        install -vDm 644 docs/_build/man/archinstall.1 -t "${pkgdir}/usr/share/man/man1/"
}
