#!/usr/bin/env python

from setuptools import setup, find_packages

requires = ['flask',
            'flask-script',
            'flask-login',
            'Flask-OAuthlib',
            'Flask-RESTful',
            'Flask-SQLAlchemy',
            'flask_debugtoolbar',
            'mock',
            'selenium',
            'cryptacular',
            'enum',
            'stripe',
            'psycopg2',
            'Babel']

setup(name='crowdlink',
      version='0.1',
      description='A product feature request and management tool',
      author='Isaac Cook',
      author_email='isaac@simpload.com',
      install_requires=requires,
      dependency_links=["https://code.stripe.com/stripe/stripe-1.9.8.tar.gz#egg=stripe-1.9.8"],
      url='http://www.python.org/sigs/distutils-sig/',
      packages=find_packages()
     )
