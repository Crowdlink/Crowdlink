#!/bin/bash
cat util/init.sql | sudo -u postgres psql -d template1
echo "testing\n" | psql -U crowdlink -W -c "CREATE EXTENSION hstore;" 
