CREATE SCHEMA IF NOT EXISTS test_schema;

CREATE TABLE IF NOT EXISTS test_schema.users (
    id      INT PRIMARY KEY,
    name    VARCHAR(255),
    email   VARCHAR(255),
    tel     VARCHAR(255)
);
