# TicketHunter 票务监控系统

## 项目简介
TicketHunter是一个智能票务监控和分析系统，专门用于追踪和分析小红书平台上的票务信息。该系统能够自动检测、分析和管理演出票务相关信息，为用户提供实时的票务监控服务。

## 主要功能
- 🤖 智能关键词优化：使用智谱AI自动分析用户意图，优化搜索关键词
- 🎫 智能票务识别：使用智谱AI模型自动识别和分析票务信息
- ⚡ 高性能处理：5并发处理笔记内容，大幅提升分析速度
- 🔍 实时搜索：支持关键词搜索票务信息
- 📊 数据展示：直观展示票务数据和搜索结果
- 🔄 实时更新：使用SSE（Server-Sent Events）实现实时数据推送
- 🛡️ 安全防护：内置访问频率限制和错误处理机制
- 💾 数据持久化：使用SQLite数据库存储历史数据

## 技术栈
- 后端：Flask
- 数据库：SQLite
- AI模型：智谱AI API
- 数据源：xiaohongshu-mcp (本地 MCP 服务)
- 前端：Bootstrap + jQuery
- 实时通信：Server-Sent Events (SSE)

## 环境要求
- Python 3.8+
- xiaohongshu-mcp 服务 (需要本地部署)
- 现代浏览器（支持SSE）
- Windows/Linux/MacOS

## 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/YiCheng996/tickethunter.git
cd tickethunter
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 部署 xiaohongshu-mcp 服务

参考 [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) 项目文档，部署本地 MCP 服务：

```bash
# 下载并启动 xiaohongshu-mcp 服务
# 默认监听地址：http://localhost:18060/mcp
```

详细部署步骤请参考：[xiaohongshu-mcp README](https://github.com/xpzouying/xiaohongshu-mcp#readme)

### 4. 配置API密钥

修改`config.py`中的配置信息：
```python
class Config:
    # 智谱AI API配置
    ZHIPU_API_KEY = 'your_zhipu_api_key'  # 填写你的智谱AI API密钥
       
    # 小红书 MCP 服务配置
    MCP_XIAOHONGSHU_URL = 'http://localhost:18060/mcp'  # MCP 服务地址
```

### 5. 启动应用
```bash
python app.py
```

### 6. 访问系统
启动成功后，访问：http://localhost:5000

## 目录结构
```
tickethunter/
├── app.py                        # Flask主应用
├── config.py                     # 配置文件
├── database.py                   # 数据库模型
├── prompts.py                    # AI 提示词配置文件
├── mcp_client.py                 # 小红书 MCP 客户端
├── requirements.txt              # 项目依赖
├── test_mcp.py                   # MCP 服务测试脚本
├── test_keyword_optimization.py  # 关键词优化测试脚本
├── templates/                    # 前端模板
│   └── index.html               # 主页面
└── log/                         # 日志目录
    └── tickethunter.log
```

## 功能说明

### 1. 搜索功能
- 支持关键词搜索
- **智能关键词优化**：输入任意描述，AI 自动提取核心关键词
  - 例如："周杰伦演唱会有人转让票吗" → "周杰伦演唱会转让票"
  - 去除冗余词汇，保留核心信息
- 实时显示搜索进度
- 自动分析票务信息

### 2. 任务管理
- 查看任务状态
- 停止运行中的任务
- 删除历史任务

### 3. 数据展示
- 票务信息表格展示
- 支持查看原文链接
- 按时间排序

### 4. 实时更新
- SSE实时推送
- 自动更新任务状态
- 实时显示新票务信息

## 常见问题

### 1. MCP 服务连接失败
- 确认 xiaohongshu-mcp 服务已启动
- 检查服务地址配置是否正确 (默认 http://localhost:18060/mcp)
- 查看 MCP 服务日志排查问题
- 运行 `python test_mcp.py` 测试 MCP 服务连接

### 2. API调用失败
- 检查智谱AI API密钥是否正确配置
- 确认API密钥额度是否充足
- 查看日志文件获取详细错误信息

### 3. 搜索无结果
- 确认关键词是否准确
- 检查 MCP 服务是否正常运行
- 确认 xiaohongshu-mcp 已完成登录认证
- 查看后台日志排查原因

## 开发指南

### 日志系统
- 日志文件位置：`log/tickethunter.log`
- 使用rotating handler防止日志文件过大
- 同时输出到控制台和文件

### 错误处理
- API调用错误自动重试
- 数据库操作事务管理
- SSE连接自动重连

### 数据安全
- 防SQL注入
- 请求频率限制
- 敏感信息加密存储

## 许可证
MIT License

## 联系方式
如有问题或建议，请提交Issue或Pull Request
