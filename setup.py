#!/usr/bin/env python

from setuptools import setup, find_packages

requires = ['pymongo',
            'flask',
            'flask_mongoengine',
            'mongoengine',
            'flask-script',
            'yota',
            'cryptacular']

setup(name='featurelet',
      version='0.1',
      description='A product feature request and management tool',
      author='Isaac Cook',
      author_email='isaac@simpload.com',
      install_requires=requires,
      url='http://www.python.org/sigs/distutils-sig/',
      packages=find_packages()
     )
