#!/usr/bin/env python

from setuptools import setup, find_packages

requires = ['flask',
            'six',
            'sqlalchemy']

setup(name='lever',
      version='0.2.2',
      description='A tool for exposing SQLAlchemy models in Flask via REST',
      author='Isaac Cook',
      author_email='isaac@crowdlink.io',
      install_requires=requires,
      url='http://www.python.org/sigs/distutils-sig/',
      packages=find_packages()
      )
