#!/usr/bin/env python
import fnmatch
import os
import json
import argparse
import six

from jinja2 import Environment, FileSystemLoader

parser = argparse.ArgumentParser(description='Preprocess all our templates')
parser.add_argument('input',
                    help='folder or file on which to run preprocessor')
parser.add_argument('filetype',
                    help='filetype to pre-process')
parser.add_argument('-v', '--verbose', action='store_true',
                    help='print each file processed')
parser.add_argument('-f', '--force', action='store_true',
                    help='ignore timestamps, just re-parse everything')
parser.add_argument('-c', '--config', default='application.json',
                    help='path to the JSON config file')
parser.add_argument('-o', '--output', default='processed',
                    help='the folder to place all the processed files')
parser.add_argument('-vv', '--very-verbose', action='store_true',
                    help='print each file processed')

args = parser.parse_args()
if args.very_verbose:
    args.verbose = True

env = Environment(loader=FileSystemLoader(os.getcwd()))
# last mod time for config
config_time = os.path.getctime(args.config)
env_vars = json.load(open(args.config))['public']

p_one = False
for root, _, filenames in os.walk(args.input):
    # construct a path for the pre-processed files to go in
    rel_root = os.path.relpath(root, os.getcwd())
    folder = os.path.join(args.output, rel_root)
    try:
        os.makedirs(folder)
    except OSError:
        pass
    else:
        if args.verbose:
            print("Created " + folder)
    for filename in fnmatch.filter(filenames, '*.' + args.filetype):
        outfile = os.path.join(folder, filename)
        infile = os.path.join(rel_root, filename)

        try:
            tm = os.path.getctime(outfile)
        except OSError:
            tm = 0
        if max(os.path.getctime(infile), config_time) > tm or args.force:
            try:
                output = env.get_template(infile).render(**env_vars)
                if not six.PY3:  # specify encoding for python 2.7
                    output = output.encode('utf8')
                open(outfile, 'w').write(output)
            except Exception:
                print("Error parsing file " + outfile)
                raise
            if args.verbose:
                p_one = True
                print("Parsed " + outfile)
        else:
            if args.very_verbose:
                print("Not changed " + outfile)

if not p_one and args.verbose:
    print("No changes made")
