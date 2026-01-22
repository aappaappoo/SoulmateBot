# 调试笔记本 (Debug Notebooks)

本目录包含用于调试和测试各个平台功能的 Jupyter Notebook 文件。

## 笔记本列表

| 文件 | 描述 | 主要功能 |
|------|------|----------|
| `01_llm_gateway_debug.ipynb` | LLM 网关调试 | Provider 管理、限流测试、Token 统计 |
| `02_conversation_debug.ipynb` | 会话管理调试 | Session 管理、Prompt 模板、上下文窗口 |
| `03_bot_config_debug.ipynb` | Bot 配置调试 | YAML 配置加载、功能检查、热重载 |
| `04_payment_debug.ipynb` | 支付系统调试 | 额度管理、订阅流程、支付模拟 |
| `05_multibot_debug.ipynb` | **多机器人开发调试** | 人设配置、技能匹配、Agent路由、批量注册 |

## 使用方法

### 1. 安装 Jupyter

```bash
pip install jupyter
```

### 2. 启动 Jupyter

```bash
cd notebooks
jupyter notebook
```

### 3. 打开笔记本

在浏览器中打开对应的 `.ipynb` 文件即可开始调试。

## 环境变量

在运行笔记本前，请确保设置以下环境变量：

```bash
# 必需
export TELEGRAM_BOT_TOKEN="your_bot_token"

# 可选 - 用于真实 API 调用
export OPENAI_API_KEY="your_openai_key"
export ANTHROPIC_API_KEY="your_anthropic_key"
export VLLM_API_URL="http://your-vllm-server:8000"
```

## 注意事项

1. 笔记本中的代码会实际调用 API，可能产生费用
2. 建议使用测试账号和小额 Token 限制
3. 调试完成后记得清理测试数据

## 笔记本内容说明

### 01_llm_gateway_debug.ipynb
- LLM Gateway 模块导入和初始化
- Provider 注册（OpenAI、Anthropic、vLLM）
- Rate Limiter 限流测试
- Token Counter 统计测试
- 完整的 LLM 请求/响应流程

### 02_conversation_debug.ipynb
- SessionManager 会话管理
- 消息历史管理
- Prompt 模板渲染
- Context Window 上下文管理
- 会话数据导出

### 03_bot_config_debug.ipynb
- YAML 配置文件加载
- Bot 配置详情查看
- 功能开关检查
- 配置热重载测试
- 自定义配置创建

### 04_payment_debug.ipynb
- 订阅计划查看
- 用户额度管理
- 支付流程模拟
- 订阅过期处理
- 完整支付流程演示

### 05_multibot_debug.ipynb
- 多机器人配置加载和验证
- 人设（personality）配置测试
- 技能（skills）匹配测试
- Agent 系统路由测试
- 数据库状态检查
- 新机器人模板生成
- 批量创建和注册机器人
