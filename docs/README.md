## Dependencies

In order to build the docs locally, you need to have the following installed:

- [sphinx-doc](https://www.sphinx-doc.org/en/master/usage/installation.html)
- [sphinx-rdt-theme](https://pypi.org/project/sphinx-rtd-theme/)

For example, you may install these dependencies using pip:
```
pip install -U sphinx sphinx-rtd-theme
```

For other installation methods refer to the docs of the dependencies.

## Build

In `archinstall/docs`, run `make html` (or specify another target) to build locally. The build files will be in `archinstall/docs/_build`. Open `_build/html/index.html` with your browser to see your changes in action.