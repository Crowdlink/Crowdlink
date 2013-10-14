#!/usr/bin/env python

from setuptools import setup, find_packages

requires = ['pymongo',
            'flask',
            'mock',
            'flask_mongoengine',
            'mongoengine',
            'flask-script',
            'flask-login',
            'yota>=0.3',
            'selenium',
            'cryptacular',
            'Babel']

setup(name='featurelet',
      version='0.1',
      description='A product feature request and management tool',
      author='Isaac Cook',
      author_email='isaac@simpload.com',
      install_requires=requires,
      dependency_links=["https://github.com/icook/yota/tarball/0.3#egg=yota-0.3"],
      url='http://www.python.org/sigs/distutils-sig/',
      packages=find_packages()
     )
