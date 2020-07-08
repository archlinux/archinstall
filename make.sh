#!/bin/bash
rm -rf archinstall.egg-info/ build/ dist/
python3 setup.py sdist bdist_wheel

echo 'python3 -m twine upload dist/*'
