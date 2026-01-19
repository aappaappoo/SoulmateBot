# Database Migrations

This directory contains SQL migration scripts for the SoulmateBot database.

## Available Migrations

### `fix_subscription_tier_enum.sql`
**Purpose:** Converts the `subscription_tier` column from PostgreSQL ENUM type to VARCHAR(20)

**When to use:** 
- When you see the error: `invalid input value for enum subscriptiontier: "free"`
- After upgrading from an older version that used SQLEnum

**How to run:**
```bash
psql -U your_username -d your_database -f migrations/fix_subscription_tier_enum.sql
```

## Before Running Migrations

Always backup your database first:
```bash
pg_dump -U your_username -d your_database > backup_$(date +%Y%m%d).sql
```

## Migration Order

Run migrations in this order:
1. `fix_subscription_tier_enum.sql` - Initial fix for ENUM issue

## Support

See `MIGRATION_GUIDE.md` for detailed instructions and troubleshooting.
