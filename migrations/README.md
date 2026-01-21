# Database Migrations
# 数据库迁移脚本

This directory contains SQL migration scripts for the SoulmateBot database.

本目录包含 SoulmateBot 数据库的 SQL 迁移脚本。

## Available Migrations / 可用迁移脚本

### `fix_subscription_tier_enum.sql`
**Purpose / 目的:** Converts the `subscription_tier` column from PostgreSQL ENUM type to VARCHAR(20)

将 `subscription_tier` 列从 PostgreSQL ENUM 类型转换为 VARCHAR(20)

**When to use / 何时使用:** 
- When you see the error: `invalid input value for enum subscriptiontier: "free"`
- After upgrading from an older version that used SQLEnum

### `add_uuid_version_session.sql` ⭐ 新增
**Purpose / 目的:** 
1. 为 User 和 Bot 表添加 UUID 字段，用于外部 API 引用（替代直接暴露内部 ID）
2. 添加 version 字段实现乐观锁并发控制
3. 为 Conversation 表添加 session_id 字段，支持会话隔离
4. 添加优化的复合索引，提升高并发场景查询性能
5. 为所有字段添加中文备注说明

**When to use / 何时使用:** 
- 升级到支持并发控制的新版本时
- 需要使用 UUID 作为外部 API 引用时
- 需要会话隔离功能时

### `migrate_to_multibot.py`
**Purpose / 目的:** Python script to migrate existing data to multi-bot architecture

迁移现有数据到多机器人架构

**How to run / 运行方式:**
```bash
cd /path/to/SoulmateBot
python migrations/migrate_to_multibot.py
```

## Before Running Migrations / 运行前准备

Always backup your database first / 请先备份数据库:
```bash
pg_dump -U your_username -d your_database > backup_$(date +%Y%m%d).sql
```

## Migration Order / 迁移顺序

Run migrations in this order / 按以下顺序运行迁移:
1. `fix_subscription_tier_enum.sql` - Initial fix for ENUM issue
2. `add_uuid_version_session.sql` - Add UUID, version control and session isolation ⭐ 新增
3. `migrate_to_multibot.py` - Migrate to multi-bot architecture

## UUID vs MD5 选择说明

本项目使用 **UUID** 而非 MD5 作为外部引用标识，原因如下：

1. **唯一性保证**: UUID (v4) 提供 122 位随机性，碰撞概率极低
2. **无需输入源**: MD5 需要源字符串进行哈希，UUID 可直接生成
3. **标准化**: UUID 是 RFC 4122 标准，有广泛的库支持
4. **性能**: 36 字符的 UUID 与 32 字符的 MD5 长度相近，索引性能相当

如果您更倾向使用 MD5，可以修改 `src/models/database.py` 中的 `generate_uuid` 函数。

## Support / 技术支持

See `MIGRATION_GUIDE.md` for detailed instructions and troubleshooting.

详细说明和故障排除请参阅 `MIGRATION_GUIDE.md`。
