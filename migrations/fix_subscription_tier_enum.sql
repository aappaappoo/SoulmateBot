-- Migration script to fix subscription_tier ENUM type issue
-- This script converts the subscription_tier column from ENUM to VARCHAR

BEGIN;

-- Step 1: Check if the column is using ENUM type
DO $$
BEGIN
    -- Add a temporary column
    ALTER TABLE users ADD COLUMN subscription_tier_temp VARCHAR(20);
    
    -- Copy data from old column to new column
    UPDATE users SET subscription_tier_temp = subscription_tier::text;
    
    -- Drop the old column (this will also drop the constraint)
    ALTER TABLE users DROP COLUMN subscription_tier;
    
    -- Rename the temp column
    ALTER TABLE users RENAME COLUMN subscription_tier_temp TO subscription_tier;
    
    -- Set default value
    ALTER TABLE users ALTER COLUMN subscription_tier SET DEFAULT 'free';
    
    -- Add NOT NULL constraint if needed
    ALTER TABLE users ALTER COLUMN subscription_tier SET NOT NULL;
    
    RAISE NOTICE 'Successfully migrated subscription_tier from ENUM to VARCHAR';
END $$;

-- Step 2: Drop the ENUM type if it exists and is not used by other tables
DROP TYPE IF EXISTS subscriptiontier CASCADE;

COMMIT;
