#!/bin/bash -x
recess less/bootstrap/bootstrap.less --compile --compress > static/lib/css/bootstrap.min.css
rm -rf static/css/*
compass compile --force --css-dir="static/css" --sass-dir="scss" --images-dir="static/img" -s compressed
coffee -c  -o ./static/js/ ./coffee/main.coffee
coffee -c  -o ./static/js/ ./coffee/controllers.coffee
coffee -c  -o ./static/js/ ./coffee/app.coffee
coffee -c  -o ./static/js/ ./coffee/services.coffee
coffee -c  -o ./static/js/ ./coffee/lib.coffee
