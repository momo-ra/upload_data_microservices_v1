-- Migration: Remove workspace_id from time_series table
-- Date: 2025-09-11
-- Description: Remove workspace_id column and related constraints from time_series table

-- Step 1: Drop the existing primary key constraint
ALTER TABLE time_series DROP CONSTRAINT IF EXISTS time_series_pkey;

-- Step 2: Drop the foreign key constraint to workspaces
ALTER TABLE time_series DROP CONSTRAINT IF EXISTS time_series_workspace_id_fkey;

-- Step 3: Drop the index on workspace_id and tag_id
DROP INDEX IF EXISTS idx_time_series_workspace_tag;

-- Step 4: Drop the workspace_id column
ALTER TABLE time_series DROP COLUMN IF EXISTS workspace_id;

-- Step 5: Create new primary key constraint on tag_id and timestamp
ALTER TABLE time_series ADD CONSTRAINT time_series_pkey PRIMARY KEY (tag_id, timestamp);

-- Step 6: Create new index on tag_id only
CREATE INDEX IF NOT EXISTS idx_time_series_tag ON time_series (tag_id);

-- Step 7: Update the comment on the table
COMMENT ON TABLE time_series IS 'Time Series - Plant Database, Plant-wide (no workspace restriction)';

