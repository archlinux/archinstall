#!/bin/bash
rm -rf archinstall.egg-info/ build/ dist/
python3 setup.py sdist bdist_wheel
sudo pip install --upgrade dist/*.whl
ls -l /usr/lib/python3.8/site-packages/archinstall
#echo 'python3 -m twine upload dist/*'
