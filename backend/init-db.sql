-- Initial database setup for TrackCast development
-- This script runs when the PostgreSQL container starts for the first time

-- Create the database (already done by POSTGRES_DB env var)
-- CREATE DATABASE trackcast_dev;

-- Connect to the database
\c trackcast_dev;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create a schema for application tables (optional)
-- CREATE SCHEMA IF NOT EXISTS trackcast;

-- Grant permissions to the trackcast user
GRANT ALL PRIVILEGES ON DATABASE trackcast_dev TO trackcast;
GRANT ALL PRIVILEGES ON SCHEMA public TO trackcast;

-- Note: The actual table schema will be created by the application
-- via SQLAlchemy/Alembic migrations when the service starts