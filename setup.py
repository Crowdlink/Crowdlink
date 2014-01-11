#!/usr/bin/env python

from setuptools import setup, find_packages

requires = ['flask',
            'flask-script',
            'flask-login',
            'Flask-OAuthlib',
            'Flask-SQLAlchemy',
            'flask_debugtoolbar',
            'pyyaml',
            'decorator',
            'cryptacular',
            'psycopg2',
            'lever']

setup(name='crowdlink',
      version='0.1',
      description='A product feature request and management tool',
      author='Isaac Cook',
      author_email='isaac@crowdlink.io',
      install_requires=requires,
      url='http://www.python.org/sigs/distutils-sig/',
      packages=find_packages()
      )
