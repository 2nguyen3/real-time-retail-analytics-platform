-- Run once by a database administrator. Creates an isolated schema owned by the application role.
-- psql variables: app_role, reader_role
\set ON_ERROR_STOP on
GRANT :"app_role" TO CURRENT_USER;
CREATE SCHEMA IF NOT EXISTS bench_r11 AUTHORIZATION :"app_role";
GRANT USAGE ON SCHEMA bench_r11 TO :"reader_role";
\dn+ bench_r11
