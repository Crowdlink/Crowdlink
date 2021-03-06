DROP DATABASE IF EXISTS crowdlink;
DROP DATABASE IF EXISTS crowdlink_testing;
CREATE USER crowdlink WITH PASSWORD 'testing';
CREATE DATABASE crowdlink;
GRANT ALL PRIVILEGES ON DATABASE crowdlink to crowdlink;
ALTER ROLE crowdlink SUPERUSER;
-- Create a testing database to be different than dev
CREATE DATABASE crowdlink_testing;
GRANT ALL PRIVILEGES ON DATABASE crowdlink to crowdlink;
-- Add HSTORE to both databases
\c crowdlink
CREATE EXTENSION hstore;
\c crowdlink_testing
CREATE EXTENSION hstore;
