CREATE USER crowdlink WITH PASSWORD 'testing';
CREATE DATABASE crowdlink;
GRANT ALL PRIVILEGES ON DATABASE crowdlink to crowdlink;
-- Create a testing database to be different than dev
CREATE DATABASE crowdlink_testing;
GRANT ALL PRIVILEGES ON DATABASE crowdlink to crowdlink;
-- Add HSTORE to both databases
\c crowdlink
drop schema public cascade;
create schema public;
CREATE EXTENSION hstore;
\c crowdlink_testing
drop schema public cascade;
create schema public;
CREATE EXTENSION hstore;
