# Maintainer: Anton Hvornum anton@hvornum.se
# Contributor: Anton Hvornum anton@hvornum.se
pkgname="archinstall"
pkgver="v2.0.3"
pkgdesc="Installs a pre-built binary of ${pkgname}"
pkgrel=1
url="https://github.com/Torxed/archinstall"
license=('GPLv3')
provides=("${pkgname}")
md5sums=('SKIP')
arch=('x86_64')
source=("${pkgname}-${pkgver}-x86_64.tar.gz")
#makedepends=('python>=3.8')

package() {
	cd "${pkgname}-${pkgver}-x86_64"

	mkdir -p "${pkgdir}/var/lib/archinstall/"
	mkdir -p "${pkgdir}/usr/bin"

	mv * "${pkgdir}/var/lib/archinstall/"

	echo '#!/bin/bash' > "${pkgdir}/usr/bin/archinstall"
	echo '(cd /var/lib/archinstall && exec ./archinstall)' >> "${pkgdir}/usr/bin/archinstall"

	chmod +x "${pkgdir}/var/lib/archinstall/archinstall"
	chmod +x "${pkgdir}/usr/bin/archinstall"
}
