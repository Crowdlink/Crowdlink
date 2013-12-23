#!/usr/bin/env python
import fnmatch
import os
import json
import argparse

from jinja2 import Environment, FileSystemLoader

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('folder',
                    help='folder in which to run preprocessor')
parser.add_argument('filetype',
                    help='filetype to pre-process')
parser.add_argument('-v', '--verbose', action='store_true',
                    help='print each file processed')

args = parser.parse_args()

env = Environment(loader=FileSystemLoader(os.getcwd()))
env_vars = json.loads(file('application.json').read())['public']

for root, _, filenames in os.walk(args.folder):
    # construct a path for the pre-processed files to go in
    rel_root = os.path.relpath(root, os.getcwd())
    folder = os.path.join('processed', rel_root)
    try:
        os.makedirs(folder)
    except OSError:
        pass
    else:
        if args.verbose:
            print "Created " + folder
    for filename in fnmatch.filter(filenames, '*.' + args.filetype):
        processed = os.path.join(folder, filename)
        try:
            open(processed, 'w').write(
                env.get_template(os.path.join(rel_root, filename)).render(**env_vars).encode('utf-8'))
        except Exception:
            print "Error parsing file " + processed
            raise
        if args.verbose:
            print "Parsed " + processed