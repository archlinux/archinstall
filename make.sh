#!/bin/bash
# Description: Binary builder for https://archlinux.life/bin/

VERSION=$(cat VERSION)

rm -rf archinstall.egg-info/ build/ src/ pkg/ dist/ archinstall.build/ "archinstall-v${VERSION}-x86_64/" *.pkg.*.xz archinstall-*.tar.gz

#nuitka3 --standalone --show-progress archinstall
#cp -r examples/ archinstall.dist/
#mv archinstall.dist "archinstall-v${VERSION}-x86_64"
#tar -czvf "archinstall-v${VERSION}.tar.gz" "archinstall-v${VERSION}-x86_64"

# makepkg -f
python3 setup.py sdist bdist_wheel
echo 'python3 -m twine upload dist/* && rm -rf dist/'
python3 -m twine upload dist/* && rm -rf dist/

rm -rf archinstall.egg-info/ build/ src/ pkg/ archinstall.build/ "archinstall-v${VERSION}-x86_64/"
