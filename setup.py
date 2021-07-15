from setuptools import setup
import os

base_dir = os.path.dirname(__file__)

setup(
    name="bintable",
    version="0.1.0",
    description="A numpy binary format for astropy tables",
    url="https://github.com/Mortal/bintable",
    author="Mathias Rav <m@git.strova.dk>",
    license="GPLv2+",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
    ],
    py_modules=["bintable"],
)
