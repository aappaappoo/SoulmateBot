# Database Migration Guide

## Issue: PostgreSQL ENUM Type Error

If you're experiencing the error:
```
psycopg2.errors.InvalidTextRepresentation: invalid input value for enum subscriptiontier: "free"
```

This means your PostgreSQL database needs to be migrated.

## Migration Steps

### Option 1: Using the SQL Migration Script (Recommended)

1. **Backup your database first:**
   ```bash
   pg_dump -U your_username -d your_database > backup_$(date +%Y%m%d).sql
   ```

2. **Run the migration script:**
   ```bash
   psql -U your_username -d your_database -f migrations/fix_subscription_tier_enum.sql
   ```

3. **Verify the migration:**
   ```sql
   \d users
   ```
   
   You should see `subscription_tier` as `character varying(20)` instead of `subscriptiontier`

4. **Restart your bot:**
   ```bash
   python -m src.bot.main
   ```

### Option 2: Fresh Database (If no important data)

If you don't have important data to preserve:

1. **Drop all tables:**
   ```sql
   DROP TABLE IF EXISTS payments CASCADE;
   DROP TABLE IF EXISTS usage_records CASCADE;
   DROP TABLE IF EXISTS conversations CASCADE;
   DROP TABLE IF EXISTS users CASCADE;
   DROP TYPE IF EXISTS subscriptiontier CASCADE;
   ```

2. **Reinitialize the database:**
   ```bash
   python -c "from src.database import init_db; init_db()"
   ```

### Option 3: Using Alembic (For production)

If you're using Alembic for database migrations:

1. **Generate a migration:**
   ```bash
   alembic revision --autogenerate -m "Convert subscription_tier from ENUM to VARCHAR"
   ```

2. **Review and edit the migration file** if needed

3. **Apply the migration:**
   ```bash
   alembic upgrade head
   ```

## Verification

After migration, test the bot:

1. Send `/start` command to your bot
2. Send a regular message
3. Check that no errors appear in the logs

## Troubleshooting

### If you still see ENUM errors:

1. **Check if ENUM type still exists:**
   ```sql
   SELECT typname FROM pg_type WHERE typname = 'subscriptiontier';
   ```

2. **If it exists, force drop it:**
   ```sql
   DROP TYPE subscriptiontier CASCADE;
   ```

3. **Restart PostgreSQL** (if necessary):
   ```bash
   sudo systemctl restart postgresql
   ```

### If you need to rollback:

Restore from backup:
```bash
psql -U your_username -d your_database < backup_YYYYMMDD.sql
```

## Support

If you encounter issues, please check:
- PostgreSQL version compatibility
- User permissions for ALTER TABLE operations
- Any custom ENUM types you may have created

For more help, please open an issue on GitHub.
