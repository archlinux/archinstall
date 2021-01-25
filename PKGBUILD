# Maintainer: Anton Hvornum <anton@hvornum.se>
# Contributor: Giancarlo Razzolini <grazzolini@archlinux.org>
# Contributor: demostanis worlds <demostanis@protonmail.com>

pkgbase=archinstall-git
pkgname=('archinstall-git' 'python-archinstall-git')
pkgver=$(git describe --long | sed 's/\([^-]*-g\)/r\1/;s/-/./g')
pkgrel=1
pkgdesc="Just another guided/automated Arch Linux installer with a twist"
arch=('any')
url="https://github.com/Torxed/archinstall"
license=('GPL')
depends=('python')
makedepends=('python-setuptools')

build() {
	cd "$startdir"

        python setup.py build
}


package_archinstall-git() {
        depends=('python-archinstall-git')
        conflicts=('archinstall')
	cd "$startdir"

        mkdir -p "${pkgdir}/usr/bin"
        
        # Install a guided profile
	cat - > "${pkgdir}/usr/bin/archinstall" <<EOF
#!/bin/sh
python -m archinstall $@
EOF

	chmod +x "${pkgdir}/usr/bin/archinstall"
}

package_python-archinstall-git() {
        conflicts=('python-archinstall')
	cd "$startdir"

        python setup.py install --prefix=/usr --root="${pkgdir}" --optimize=1 --skip-build
}
