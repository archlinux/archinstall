#!/bin/bash
# Description: Crude build/maker script for PKGBUILD dependencies and stuff.

rm -rf archinstall.egg-info/ build/ src/ pkg/ dist/ archinstall.build/ archinstall-v2.0.3/ *.pkg.*.xz archinstall-*.tar.gz

python3 setup.py sdist bdist_wheel
nuitka3 --standalone --show-progress archinstall

mv archinstall.dist archinstall-v2.0.3
tar -czvf archinstall-v2.0.3.tar.gz archinstall-v2.0.3
makepkg -f

rm -rf archinstall.egg-info/ build/ dist/ src/ pkg/ archinstall.build/ archinstall-v2.0.3/ archinstall-*.tar.gz
echo 'python3 -m twine upload dist/*'
