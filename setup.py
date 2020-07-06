import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="archinstall",
    version="2.0.1",
    author="Anton Hvornum",
    author_email="anton@hvornum.se",
    description="Arch Linux installer - guided, templates etc.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Torxed/archinstall",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires='>=3.8',
)