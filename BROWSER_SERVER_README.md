# Browser Control Server

这是一个基于 Playwright 和 aiohttp 的浏览器控制服务器，用于提供 HTTP API 来控制浏览器执行自动化任务。

## 特性

- ✅ 基于 Playwright 的浏览器自动化
- ✅ HTTP API 端点，易于集成
- ✅ 支持页面快照（accessibility tree）
- ✅ 支持页面操作（click, type, scroll, hover, press）
- ✅ ref 引用系统，精确定位页面元素
- ✅ 兼容现有 `tools.py` 客户端
- ✅ 健康检查端点

## 安装依赖

```bash
pip install aiohttp playwright loguru
python -m playwright install chromium
```

## 启动服务器

```bash
python browser_server.py
```

服务器将在 `http://localhost:9222` 上监听。

## API 文档

### 统一入口（兼容现有 tools.py）

**POST /browser**

请求体格式：
```json
{
    "action": "start|navigate|snapshot|act|close",
    "url": "...",           // navigate 时使用
    "ref": "e1",            // act 时元素引用
    "actKind": "click",     // act 时操作类型
    "value": "...",         // type 时输入值
    "coordinate": "x,y"     // 备选坐标定位
}
```

### 独立路由（openclaw 风格）

#### POST /start
启动浏览器实例

响应示例：
```json
{
    "success": true,
    "message": "Browser started successfully"
}
```

#### POST /navigate
导航到指定 URL

请求体：
```json
{
    "url": "https://www.example.com"
}
```

响应示例：
```json
{
    "success": true,
    "url": "https://www.example.com",
    "title": "Example Domain"
}
```

#### GET /snapshot
获取页面快照（accessibility tree with ref IDs）

响应示例：
```json
{
    "success": true,
    "elements": [
        {
            "ref": "e1",
            "role": "button",
            "name": "Click Me"
        },
        {
            "ref": "e2",
            "role": "textbox",
            "name": "Enter text"
        }
    ],
    "count": 2
}
```

#### POST /act
执行页面操作

请求体：
```json
{
    "kind": "click|type|hover|press|scroll",
    "ref": "e1",          // 元素引用 ID
    "value": "...",       // type 时的文本或 press 时的按键
    "coordinate": "x,y"   // 备选坐标定位
}
```

支持的操作类型：
- `click` - 点击元素
- `type` - 输入文本
- `hover` - 悬停在元素上
- `press` - 按下键盘按键（需要 value 参数，如 "Enter", "Tab"）
- `scroll` / `scrollIntoView` - 滚动到元素可见

响应示例：
```json
{
    "success": true,
    "action": "click",
    "ref": "e1"
}
```

#### POST /stop 或 POST /close
关闭浏览器

响应示例：
```json
{
    "success": true,
    "message": "Browser closed successfully"
}
```

#### GET /health 或 GET /
健康检查

响应示例：
```json
{
    "status": "ok",
    "browser_connected": true
}
```

## 使用示例

### 使用 curl 测试

```bash
# 1. 启动浏览器
curl -X POST http://localhost:9222/browser \
  -H "Content-Type: application/json" \
  -d '{"action": "start"}'

# 2. 导航到网页
curl -X POST http://localhost:9222/browser \
  -H "Content-Type: application/json" \
  -d '{"action": "navigate", "url": "https://www.baidu.com"}'

# 3. 获取页面快照
curl -X GET http://localhost:9222/snapshot

# 4. 点击元素（假设 e5 是搜索框）
curl -X POST http://localhost:9222/browser \
  -H "Content-Type: application/json" \
  -d '{"action": "act", "actKind": "type", "ref": "e5", "value": "hello"}'

# 5. 关闭浏览器
curl -X POST http://localhost:9222/browser \
  -H "Content-Type: application/json" \
  -d '{"action": "close"}'
```

### 使用 Python 客户端

```python
import asyncio
from task_engine.executors.agent_executor.tools import browser_tool

async def main():
    # 启动浏览器
    await browser_tool(action="start")
    
    # 导航到网页
    await browser_tool(action="navigate", url="https://www.example.com")
    
    # 获取页面快照
    snapshot = await browser_tool(action="snapshot")
    print(snapshot)
    
    # 点击按钮
    await browser_tool(action="act", act_kind="click", ref="e1")
    
    # 输入文本
    await browser_tool(action="act", act_kind="type", ref="e2", value="Hello")
    
    # 关闭浏览器
    await browser_tool(action="close")

asyncio.run(main())
```

## 架构设计

借鉴 [openclaw](https://github.com/aappaappoo/openclaw) 项目的设计模式：

1. **独立 HTTP 服务** - aiohttp server 监听指定端口
2. **分离式路由** - 按功能分组的路由处理器
3. **Playwright 驱动** - 使用 Playwright 控制浏览器
4. **ref 引用系统** - snapshot 返回带 ref ID 的元素列表，act 通过 ref 定位
5. **健康检查端点** - 返回服务状态

## 注意事项

- 服务器使用 headless Chromium
- 默认视口大小：1280x720
- 默认语言环境：zh-CN
- 浏览器实例在首次 start 时创建，保持单例
- 每次 snapshot 会刷新 ref 映射表

## 故障排除

### 无法连接到服务器

确保服务器已启动：
```bash
python browser_server.py
```

检查服务器日志，确认服务器正在监听端口 9222。

### Playwright 未安装

```bash
pip install playwright
python -m playwright install chromium
```

### 元素定位失败

- 先调用 `snapshot` 获取最新的页面元素列表
- 确认使用正确的 ref ID
- 检查元素是否在视口内（可能需要先滚动）

## 配置

可以通过环境变量 `BROWSER_SERVER_URL` 或 `config/settings.py` 中的 `browser_server_url` 配置服务器地址。

默认值：`http://localhost:9222`
