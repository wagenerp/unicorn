#!/usr/bin/env python3
import sys
from setuptools import setup, find_packages

setup(
  name='unicorn',
  version='0.2',
  packages=find_packages(where='py'),
  package_dir={'': 'py'},
  extras_require={},
  install_requires=[],
  url='https://github.com/wagenerp/unicorn',
  maintainer='Peter Wagener',
  maintainer_email='mail@peterwagener.net',
  python_requires='>=3.5',
  classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Communications",
        "Topic :: Home Automation",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
  ]
)
