#!/bin/bash
# Description: Crude build/maker script for PKGBUILD dependencies and stuff.

rm -rf archinstall.egg-info/ build/ src/ pkg/ dist/ archinstall.build/ archinstall-v2.0.4rc3-x86_64/ *.pkg.*.xz archinstall-*.tar.gz

nuitka3 --standalone --show-progress archinstall
cp -r examples/ archinstall.dist/
mv archinstall.dist archinstall-v2.0.4rc3-x86_64
tar -czvf archinstall-v2.0.4rc3.tar.gz archinstall-v2.0.4rc3-x86_64
makepkg -f

python3 setup.py sdist bdist_wheel
echo 'python3 -m twine upload dist/*'

rm -rf archinstall.egg-info/ build/ dist/ src/ pkg/ archinstall.build/ archinstall-v2.0.4rc3-x86_64/
