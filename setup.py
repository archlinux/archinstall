import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="archinstall-Torxed", # Replace with your own username
    version="2.0.0",
    author="Anton Hvornum",
    author_email="anton@hvornum.se",
    description="Arch Linux installer - guided, templates etc.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Torxed/archinstall",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPL 3.0 License",
        "Operating System :: Arch Linux",
    ],
    python_requires='>=3.8',
)