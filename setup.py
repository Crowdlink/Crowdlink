#!/usr/bin/env python

from setuptools import setup, find_packages


setup(name='crowdlink',
      version='0.1',
      description='A product feature request and management tool',
      author='Isaac Cook',
      author_email='isaac@crowdlink.io',
      url='http://www.python.org/sigs/distutils-sig/',
      dependency_links=[
          'http://code.ibcook.pri/icook/lever/repository/archive#egg=lever-0.1'
      ],
      packages=find_packages()
      )
