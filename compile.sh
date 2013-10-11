recess less/bootstrap/bootstrap.less --compile --compress > static/lib/css/bootstrap.min.css
rm -rf static/css/*
compass compile --force --css-dir="static/css" --sass-dir="scss" --images-dir="static/img" -s compressed
