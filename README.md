# AI 图像生成服务

基于 Together AI 的图像生成服务，专门设计用于与 Cursor MCP 服务集成。支持自定义图片大小、保存路径等功能。

## 功能特点

- 支持高质量图像生成
- 自动重试和错误处理
- 支持批量生成多张图片
- 完整的路径和权限验证
- 详细的错误提示
- 异步处理支持

## 环境准备

### 1. Python 环境
- Python 3.8+ 
- 推荐使用 pyenv 管理 Python 版本：
```bash
# macOS 安装 pyenv
brew install pyenv

# 安装 Python
pyenv install 3.8.10
pyenv global 3.8.10
```

### 2. uv 包管理工具
uv 是一个快速的 Python 包管理器，需要先安装：

```bash
# macOS 安装 uv
brew install uv

# 或者使用 pip 安装
pip install uv
```

### 3. Together AI API 密钥
1. 访问 [Together AI API Keys](https://api.together.ai/settings/api-keys)
2. 注册/登录账号
3. 创建新的 API 密钥
4. 复制密钥并保存，格式如：`YOUR_API_KEY`

### 4. Cursor IDE
- 下载并安装 [Cursor IDE](https://cursor.sh/)
- 确保 Cursor IDE 已正确配置 Python 环境

## 安装配置

1. 克隆项目：
```bash
git clone [项目地址]
cd generate_images
```

2. 安装依赖：
```bash
uv pip install fastmcp requests
```

3. 配置 API 密钥：

在 `mcp/mcp_server.py` 中修改 `TOGETHER_API_KEY`：
```python
TOGETHER_API_KEY = "your_api_key_here"  # 替换为你的 Together AI API 密钥
```

4. 配置服务：

在 `mcp/mcp_server.py` 中可以修改以下配置：

```python
CONFIG = {
    "api": {
        "url": "https://api.together.xyz/v1/images/generations",
        "model": "black-forest-labs/FLUX.1-schnell-Free",
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 5
    },
    "image": {
        "max_width": 1024,
        "max_height": 1024,
        "default_width": 1024,
        "default_height": 1024,
        "default_steps": 2,
        "max_batch_size": 4
    },
    "output": {
        "base_folder": "你的默认保存路径",
        "allowed_extensions": [".png", ".jpg", ".jpeg"],
        "default_extension": ".png"
    }
}
```

## 运行服务

1. 开发模式运行（带调试界面）：
```bash
uv run --with fastmcp fastmcp dev ./mcp/mcp_server.py
```

2. 生产模式运行：
```bash
uv run --with fastmcp fastmcp run ./mcp/mcp_server.py
```

3. 如果端口被占用，可以指定其他端口：
```bash
PORT=5174 uv run --with fastmcp fastmcp dev ./mcp/mcp_server.py
```

## 使用说明

### 在 Cursor IDE 中使用

1. 确保服务正在运行
2. 在 Cursor IDE 中使用以下格式调用：

```python
await generate_image(
    prompt="你的图片描述",
    file_name="输出文件名.png",
    save_folder="/绝对路径/到/保存目录",
    width=1024,  # 可选
    height=1024  # 可选
)
```

### 参数说明

- `prompt`: 图片生成提示词，建议不超过500字符
- `file_name`: 保存的文件名（不含路径，如果没有后缀则默认使用.png）
- `save_folder`: 保存目录的绝对路径（例如：/Users/username/Documents/images）
- `width`: 生成图片的宽度（可选，默认1024，最大1024）
- `height`: 生成图片的高度（可选，默认1024，最大1024）

### 注意事项

1. 路径使用说明：
   - 必须使用绝对路径
   - 确保目录具有写入权限
   - 建议使用 home 目录下的路径，例如：`/Users/username/Documents/images`

2. 权限问题解决：
   - 检查目录权限：`ls -la /path/to/folder`
   - 修改目录权限：`chmod 755 /path/to/folder`
   - 确保当前用户有写入权限

3. 常见错误处理：
   - 路径不存在：检查并创建目录
   - 权限不足：检查目录权限
   - API 超时：服务会自动重试

4. Together AI API 使用注意：
   - 注意 API 调用限制
   - 保持 API 密钥安全
   - 监控 API 使用情况

## 错误排查

如果遇到问题，请检查：

1. 服务是否正常运行
2. 保存路径是否正确（必须是绝对路径）
3. 目录权限是否正确
4. 网络连接是否正常
5. API 密钥是否有效
6. Python 环境是否正确配置
7. uv 是否正确安装
8. 依赖包是否完整安装

## 日志说明

服务运行时会输出详细日志，包括：
- 请求信息
- 错误信息
- 保存路径信息
- API 响应信息

日志格式：
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

## 开发说明

1. 代码结构：
   - `mcp_server.py`: 主服务文件
   - `CONFIG`: 配置对象
   - `ImageGenerator`: 图像生成类
   - `validate_save_path`: 路径验证函数

2. 自定义开发：
   - 可以修改 CONFIG 配置
   - 可以扩展 ImageGenerator 类
   - 可以添加新的验证函数

## 问题反馈

如果遇到问题，请提供：
1. 完整的错误信息
2. 运行环境信息
3. 具体的操作步骤
4. 相关的配置信息

## 更新日志

### v1.0.0
- 初始版本发布
- 支持基本的图像生成功能
- 添加路径验证和错误处理
- 支持异步处理和批量生成
