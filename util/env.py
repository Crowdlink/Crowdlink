#!/usr/bin/env python
from jinja2 import Environment, FileSystemLoader
import os
import argparse

parser = argparse.ArgumentParser(description='Run enviromental variable preparse')
parser.add_argument('infile', help='file to parse')
parser.add_argument('outfile', help='file to produce')
args = parser.parse_args()
env = Environment(loader=FileSystemLoader(os.getcwd()))

open(args.outfile, 'w').write(
    env.get_template(args.infile).render(**os.environ).encode('utf-8'))
