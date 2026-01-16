# 贡献指南

感谢你对 SoulmateBot 项目的关注！我们欢迎所有形式的贡献。

## 如何贡献

### 报告 Bug

如果你发现了 bug，请创建一个 Issue 并包含以下信息：

- Bug 的详细描述
- 复现步骤
- 预期行为
- 实际行为
- 环境信息（操作系统、Python 版本等）
- 相关日志或截图

### 提出新功能

如果你有新功能的想法：

1. 先检查 Issues 中是否已有类似建议
2. 创建一个新 Issue，描述：
   - 功能的目的和价值
   - 预期的实现方式
   - 可能的替代方案

### 提交代码

#### 开发流程

1. **Fork 项目**
   ```bash
   # 在 GitHub 上 Fork 项目
   git clone https://github.com/YOUR_USERNAME/SoulmateBot.git
   cd SoulmateBot
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b bugfix/your-bugfix-name
   ```

3. **设置开发环境**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **编写代码**
   - 遵循项目的代码风格
   - 添加必要的注释
   - 编写或更新测试
   - 更新相关文档

5. **运行测试**
   ```bash
   # 运行所有测试
   pytest tests/
   
   # 运行特定测试
   pytest tests/test_subscription.py
   
   # 查看覆盖率
   pytest --cov=src tests/
   ```

6. **代码格式化**
   ```bash
   # 使用 Black 格式化
   black src/ tests/
   
   # 检查代码风格
   flake8 src/ tests/ --max-line-length=100
   
   # 类型检查
   mypy src/
   ```

7. **提交更改**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   # 或
   git commit -m "fix: fix bug description"
   ```

8. **推送到 GitHub**
   ```bash
   git push origin feature/your-feature-name
   ```

9. **创建 Pull Request**
   - 在 GitHub 上创建 PR
   - 填写 PR 模板
   - 等待代码审查

#### Commit Message 规范

使用语义化提交消息：

- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `style:` 代码格式（不影响功能）
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具相关

示例：
```
feat: add image generation feature
fix: resolve subscription expiry check bug
docs: update API documentation
refactor: improve database query performance
```

### 代码规范

#### Python 代码风格

- 遵循 PEP 8
- 使用 Black 进行格式化
- 行长度限制为 100 字符
- 使用类型提示

#### 文档字符串

```python
def function_name(param1: str, param2: int) -> bool:
    """
    简短描述函数功能
    
    Args:
        param1: 参数1的描述
        param2: 参数2的描述
        
    Returns:
        返回值描述
        
    Raises:
        ValueError: 什么情况下抛出
    """
    pass
```

#### 测试

- 为新功能编写测试
- 保持测试覆盖率 > 80%
- 使用描述性的测试名称

```python
def test_user_creation_with_valid_data():
    """Test that user is created successfully with valid data"""
    pass
```

### 项目结构说明

```
src/
├── bot/          # Bot 核心逻辑
├── handlers/     # 消息和命令处理
├── models/       # 数据模型
├── database/     # 数据库连接
├── ai/           # AI 服务
├── services/     # 业务服务
├── subscription/ # 订阅管理
└── utils/        # 工具函数
```

### 依赖管理

添加新依赖时：

1. 安装依赖：`pip install package-name`
2. 更新 requirements.txt：`pip freeze > requirements.txt`
3. 在 PR 中说明为什么需要这个依赖

### 文档

更新文档的时机：

- 添加新功能时
- 修改 API 时
- 更改配置选项时
- 修复重要 bug 时

需要更新的文档：

- `README.md` - 项目概述
- `API.md` - API 文档
- `DEPLOYMENT.md` - 部署指南
- 代码内的注释和文档字符串

## 代码审查

所有 PR 都需要经过代码审查：

- 至少一位维护者的批准
- 通过所有自动化测试
- 符合代码规范
- 包含必要的文档

## 发布流程

1. 更新版本号（`src/__init__.py`）
2. 更新 CHANGELOG.md
3. 创建 Git tag
4. 发布 Release
5. 部署到生产环境

## 行为准则

- 尊重所有贡献者
- 提供建设性的反馈
- 专注于代码质量而非个人
- 保持讨论主题相关

## 获取帮助

如果你有任何问题：

- 查看现有的 Issues 和 Discussions
- 创建新的 Issue 提问
- 联系项目维护者

## 许可证

贡献的代码将采用项目的 MIT 许可证。

---

再次感谢你的贡献！ 🎉
