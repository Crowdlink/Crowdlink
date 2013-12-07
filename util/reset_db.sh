#!/bin/bash
cat util/init.sql | sudo -u postgres psql -d template1
psql -U crowdlink -W -c "CREATE EXTENSION hstore;" 
