-- 数据库升级脚本
-- 添加UUID、版本控制和会话隔离字段
-- Database upgrade script for adding UUID, version control and session isolation fields

-- =============================================================================
-- 1. 用户表（users）添加新字段
-- =============================================================================

-- 添加UUID字段（外部引用标识）
ALTER TABLE users ADD COLUMN IF NOT EXISTS uuid VARCHAR(36);
COMMENT ON COLUMN users.uuid IS '外部引用UUID，用于API和外部系统交互';

-- 生成UUID（仅对现有null值）
UPDATE users SET uuid = gen_random_uuid()::text WHERE uuid IS NULL;

-- 设置UUID为非空且唯一
ALTER TABLE users ALTER COLUMN uuid SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_uuid ON users(uuid);

-- 添加乐观锁版本号字段
ALTER TABLE users ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1 NOT NULL;
COMMENT ON COLUMN users.version IS '乐观锁版本号，用于并发控制';

-- =============================================================================
-- 2. 机器人表（bots）添加新字段
-- =============================================================================

-- 添加UUID字段（外部引用标识）
ALTER TABLE bots ADD COLUMN IF NOT EXISTS uuid VARCHAR(36);
COMMENT ON COLUMN bots.uuid IS '外部引用UUID，用于API和外部系统交互';

-- 生成UUID
UPDATE bots SET uuid = gen_random_uuid()::text WHERE uuid IS NULL;

-- 设置UUID为非空且唯一
ALTER TABLE bots ALTER COLUMN uuid SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ix_bots_uuid ON bots(uuid);

-- 添加乐观锁版本号字段
ALTER TABLE bots ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1 NOT NULL;
COMMENT ON COLUMN bots.version IS '乐观锁版本号，用于并发控制';

-- =============================================================================
-- 3. 对话表（conversations）添加会话隔离字段
-- =============================================================================

-- 添加会话标识字段
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS session_id VARCHAR(64);
COMMENT ON COLUMN conversations.session_id IS '会话标识，用于区分不同对话上下文';

-- 创建会话索引
CREATE INDEX IF NOT EXISTS idx_user_session ON conversations(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_user_timestamp ON conversations(user_id, timestamp);

-- =============================================================================
-- 4. 频道表（channels）添加并发控制字段
-- =============================================================================

-- 添加乐观锁版本号字段
ALTER TABLE channels ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1 NOT NULL;
COMMENT ON COLUMN channels.version IS '乐观锁版本号，用于并发控制';

-- =============================================================================
-- 5. 使用记录表（usage_records）添加复合索引
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_user_action_date ON usage_records(user_id, action_type, date);

-- =============================================================================
-- 6. 频道机器人映射表（channel_bot_mappings）添加复合索引
-- =============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS idx_channel_bot_unique ON channel_bot_mappings(channel_id, bot_id);
CREATE INDEX IF NOT EXISTS idx_channel_active_priority ON channel_bot_mappings(channel_id, is_active, priority);

-- =============================================================================
-- 7. 为所有字段添加中文备注（PostgreSQL）
-- =============================================================================

-- users表
COMMENT ON COLUMN users.id IS '内部自增主键';
COMMENT ON COLUMN users.telegram_id IS 'Telegram用户ID';
COMMENT ON COLUMN users.username IS 'Telegram用户名';
COMMENT ON COLUMN users.first_name IS '用户名（名）';
COMMENT ON COLUMN users.last_name IS '用户姓（姓）';
COMMENT ON COLUMN users.language_code IS '用户语言偏好，默认中文';
COMMENT ON COLUMN users.subscription_tier IS '订阅等级：free/basic/premium';
COMMENT ON COLUMN users.subscription_start_date IS '订阅开始日期';
COMMENT ON COLUMN users.subscription_end_date IS '订阅结束日期';
COMMENT ON COLUMN users.is_active IS '用户是否激活';
COMMENT ON COLUMN users.created_at IS '创建时间';
COMMENT ON COLUMN users.updated_at IS '最后更新时间';

-- bots表
COMMENT ON COLUMN bots.id IS '内部自增主键';
COMMENT ON COLUMN bots.bot_token IS 'Telegram Bot Token';
COMMENT ON COLUMN bots.bot_name IS '机器人显示名称';
COMMENT ON COLUMN bots.bot_username IS 'Telegram机器人用户名';
COMMENT ON COLUMN bots.description IS '机器人描述说明';
COMMENT ON COLUMN bots.personality IS '机器人个性描述';
COMMENT ON COLUMN bots.system_prompt IS 'AI系统提示词';
COMMENT ON COLUMN bots.ai_model IS '使用的AI模型名称';
COMMENT ON COLUMN bots.ai_provider IS 'AI提供商：openai/anthropic/vllm';
COMMENT ON COLUMN bots.settings IS '其他配置项，如temperature、max_tokens等';
COMMENT ON COLUMN bots.status IS '机器人状态：active/inactive/maintenance';
COMMENT ON COLUMN bots.is_public IS '是否可被其他用户添加到频道';
COMMENT ON COLUMN bots.created_by IS '创建者用户ID';
COMMENT ON COLUMN bots.created_at IS '创建时间';
COMMENT ON COLUMN bots.updated_at IS '最后更新时间';

-- conversations表
COMMENT ON COLUMN conversations.id IS '内部自增主键';
COMMENT ON COLUMN conversations.user_id IS '关联的用户ID';
COMMENT ON COLUMN conversations.message IS '用户消息或AI回复内容';
COMMENT ON COLUMN conversations.response IS 'AI回复内容（仅用户消息时有值）';
COMMENT ON COLUMN conversations.is_user_message IS '是否为用户发送的消息';
COMMENT ON COLUMN conversations.message_type IS '消息类型：text/image/voice等';
COMMENT ON COLUMN conversations.timestamp IS '消息时间戳';

-- usage_records表
COMMENT ON COLUMN usage_records.id IS '内部自增主键';
COMMENT ON COLUMN usage_records.user_id IS '关联的用户ID';
COMMENT ON COLUMN usage_records.action_type IS '操作类型：message/image/voice等';
COMMENT ON COLUMN usage_records.count IS '操作次数';
COMMENT ON COLUMN usage_records.date IS '记录日期';

-- payments表
COMMENT ON COLUMN payments.id IS '内部自增主键';
COMMENT ON COLUMN payments.user_id IS '支付用户ID';
COMMENT ON COLUMN payments.amount IS '支付金额（单位：分）';
COMMENT ON COLUMN payments.currency IS '货币类型，默认人民币';
COMMENT ON COLUMN payments.provider IS '支付渠道：wechat/alipay等';
COMMENT ON COLUMN payments.provider_payment_id IS '支付渠道返回的支付ID';
COMMENT ON COLUMN payments.provider_order_id IS '支付渠道的订单ID';
COMMENT ON COLUMN payments.subscription_tier IS '购买的订阅等级';
COMMENT ON COLUMN payments.subscription_duration_days IS '订阅时长（天）';
COMMENT ON COLUMN payments.status IS '支付状态：pending/success/failed/refunded';
COMMENT ON COLUMN payments.created_at IS '支付创建时间';
COMMENT ON COLUMN payments.updated_at IS '最后更新时间';

-- channels表
COMMENT ON COLUMN channels.id IS '内部自增主键';
COMMENT ON COLUMN channels.telegram_chat_id IS 'Telegram聊天ID';
COMMENT ON COLUMN channels.chat_type IS '聊天类型：private/group/supergroup/channel';
COMMENT ON COLUMN channels.title IS '频道/群组标题';
COMMENT ON COLUMN channels.username IS '频道/群组用户名';
COMMENT ON COLUMN channels.owner_id IS '频道所有者用户ID';
COMMENT ON COLUMN channels.settings IS '频道配置，如路由模式、通知设置等';
COMMENT ON COLUMN channels.subscription_tier IS '频道订阅等级';
COMMENT ON COLUMN channels.subscription_start_date IS '订阅开始日期';
COMMENT ON COLUMN channels.subscription_end_date IS '订阅结束日期';
COMMENT ON COLUMN channels.is_active IS '频道是否激活';
COMMENT ON COLUMN channels.created_at IS '创建时间';
COMMENT ON COLUMN channels.updated_at IS '最后更新时间';

-- channel_bot_mappings表
COMMENT ON COLUMN channel_bot_mappings.id IS '内部自增主键';
COMMENT ON COLUMN channel_bot_mappings.channel_id IS '关联的频道ID';
COMMENT ON COLUMN channel_bot_mappings.bot_id IS '关联的机器人ID';
COMMENT ON COLUMN channel_bot_mappings.is_active IS '映射是否激活';
COMMENT ON COLUMN channel_bot_mappings.priority IS '机器人响应优先级，数字越大优先级越高';
COMMENT ON COLUMN channel_bot_mappings.routing_mode IS '路由模式：mention（需@）/auto（自动回复）/keyword（关键词触发）';
COMMENT ON COLUMN channel_bot_mappings.keywords IS '关键词列表，用于keyword模式触发';
COMMENT ON COLUMN channel_bot_mappings.settings IS '此映射的特定配置';
COMMENT ON COLUMN channel_bot_mappings.added_at IS '添加时间';
COMMENT ON COLUMN channel_bot_mappings.updated_at IS '最后更新时间';

-- 迁移完成提示
SELECT '✅ 数据库迁移完成：已添加UUID、版本控制和会话隔离字段' AS migration_status;
