# TicketHunter 工作流程说明

## 系统架构

```
用户输入关键词
    ↓
[步骤1] 智能关键词优化（智谱AI）
    ↓
优化后的关键词
    ↓
[步骤2] 小红书搜索（xiaohongshu-mcp）
    ↓
获取笔记列表（feeds）
    ↓
[步骤3] 票务信息识别（智谱AI）
    ↓
识别并保存票务信息
    ↓
实时推送给前端（SSE）
```

## 详细流程

### 步骤1：智能关键词优化

**功能**：使用智谱AI分析用户意图，优化搜索关键词

**API**：智谱AI GLM-4-Flash 模型

**输入示例**：
```
用户输入: "周杰伦演唱会有人转让票吗"
```

**优化规则**：
1. 提取核心演出名称、艺人/乐队名称
2. 去除冗余词汇（如"的票"、"求票"、"有人转让吗"等）
3. 保留关键的时间、地点信息（如城市名）
4. 如果是明星演唱会，保留明星名字
5. 如果是音乐节/展览，保留活动名称
6. 简洁明了，便于搜索

**输出示例**：
```
优化后: "周杰伦演唱会转让票"
```

**实现代码**：`app.py` - `optimize_search_keyword()`

### 步骤2：小红书内容搜索

**功能**：使用优化后的关键词在小红书平台搜索相关笔记

**服务**：xiaohongshu-mcp (本地 MCP 服务)

**接口**：`search_feeds`

**参数**：
- `keyword`: 优化后的搜索关键词
- `sort_by`: "最新"（按时间排序）

**返回数据结构**：
```json
{
  "feeds": [
    {
      "id": "笔记ID",
      "modelType": "note",
      "noteCard": {
        "displayTitle": "笔记标题",
        "user": {
          "nickname": "用户昵称",
          "userId": "用户ID"
        },
        "interactInfo": {
          "likedCount": "点赞数",
          "commentCount": "评论数"
        },
        "cover": {
          "url": "封面图片URL"
        }
      }
    }
  ],
  "count": 笔记数量
}
```

**实现代码**：
- `mcp_client.py` - `XiaohongshuMCPClient.search_feeds()`
- `app.py` - `execute_search_task()` 中调用

### 步骤3：票务信息识别

**功能**：使用智谱AI分析笔记内容，识别是否为票务转让信息

**API**：智谱AI GLM-4-Flash 模型（流式输出）

**输入**：
- 笔记标题（displayTitle）

**识别规则**：
系统会分析笔记内容，提取以下信息：
- `is_ticket_resale`: 是否为票务转让
- `event_name`: 演出名称
- `city`: 城市
- `event_date`: 演出日期（YYYY-MM-DD 格式）
- `area`: 座位区域
- `price`: 价格
- `quantity`: 数量
- `contact`: 联系方式
- `notes`: 备注

**输出示例**：
```json
{
  "is_ticket_resale": true,
  "event_name": "周杰伦嘉年华演唱会",
  "city": "上海",
  "event_date": "2024-11-15",
  "area": "内场A区",
  "price": "1200元",
  "quantity": "2张",
  "contact": "微信：xxx",
  "notes": "连座，原价转让"
}
```

**实现代码**：`app.py` - `analyze_ticket_content()`

## 数据流转

### 1. 前端 → 后端
```javascript
// 用户提交搜索
POST /start_search
{
  "keyword": "周杰伦演唱会有人转让票吗"
}
```

### 2. 后端处理流程

```python
# 1. 关键词优化
optimized_keyword = optimize_search_keyword(keyword)
# "周杰伦演唱会有人转让票吗" → "周杰伦演唱会转让票"

# 2. MCP 服务搜索
with XiaohongshuMCPClient(MCP_URL) as client:
    feeds = client.search_feeds(optimized_keyword, sort_by="最新")

# 3. 遍历每条笔记
for feed in feeds:
    # 保存笔记
    note = Note(
        note_id=feed['id'],
        description=feed['noteCard']['displayTitle'],
        note_url=f"https://www.xiaohongshu.com/explore/{feed['id']}"
    )
    
    # 分析票务信息
    ticket_info = analyze_ticket_content(note.description)
    
    if ticket_info['is_ticket_resale']:
        # 保存票务信息
        ticket = Ticket(**ticket_info)
        
        # 实时推送给前端
        notify_clients('ticket_update', ticket_data)
```

### 3. 后端 → 前端（SSE 实时推送）

**事件类型1：任务状态更新**
```javascript
// 搜索开始
{
  "type": "task_update",
  "data": {
    "task_id": 1,
    "status": "running",
    "message": "正在搜索：周杰伦演唱会转让票 (优化自: 周杰伦演唱会有人转让票吗)"
  }
}

// 搜索完成
{
  "type": "task_update",
  "data": {
    "task_id": 1,
    "status": "completed",
    "message": "搜索完成，共处理 20 条数据"
  }
}
```

**事件类型2：票务信息更新**
```javascript
{
  "type": "ticket_update",
  "data": {
    "task_id": 1,
    "ticket": {
      "event_name": "周杰伦嘉年华演唱会",
      "city": "上海",
      "event_date": "2024-11-15",
      "area": "内场A区",
      "price": "1200元",
      "quantity": "2张",
      "contact": "微信：xxx",
      "notes": "连座，原价转让",
      "note_url": "https://www.xiaohongshu.com/explore/xxx"
    }
  }
}
```

## 性能优化

### 1. 关键词优化阶段
- **模型**：GLM-4-Flash（快速响应）
- **超时时间**：30秒
- **失败处理**：使用原始关键词继续搜索

### 2. MCP 搜索阶段
- **超时时间**：120秒
- **首次搜索**：可能需要 30-60 秒（爬取数据）
- **后续搜索**：更快（缓存）

### 3. 票务识别阶段
- **流式输出**：逐步返回结果
- **并发处理**：后台线程处理多个任务

## 错误处理

### 1. 关键词优化失败
```python
try:
    optimized_keyword = optimize_search_keyword(keyword)
except Exception as e:
    # 使用原始关键词继续
    optimized_keyword = keyword
```

### 2. MCP 服务失败
```python
try:
    feeds = client.search_feeds(optimized_keyword)
except Exception as e:
    # 标记任务失败，通知用户
    workflow_execution.status = 'failed'
    notify_clients('task_update', {'status': 'failed', 'message': f'搜索失败: {str(e)}'})
```

### 3. 票务识别失败
```python
try:
    ticket_info = analyze_ticket_content(note.description)
except Exception as e:
    # 跳过该笔记，继续处理下一条
    logger.error(f"分析失败: {str(e)}")
    continue
```

## 测试工具

### 1. 测试关键词优化
```bash
python test_keyword_optimization.py "周杰伦演唱会有人转让票吗"
```

### 2. 测试 MCP 服务
```bash
python test_mcp.py
```

### 3. 完整流程测试
```bash
# 启动应用
python app.py

# 访问 http://localhost:5000
# 输入测试关键词进行搜索
```

## 日志追踪

系统在每个阶段都会记录详细日志：

```
[INFO] 开始执行搜索任务，原始关键词: 周杰伦演唱会有人转让票吗
[INFO] 开始优化搜索关键词: 周杰伦演唱会有人转让票吗
[INFO] 关键词优化成功: '周杰伦演唱会有人转让票吗' -> '周杰伦演唱会转让票'
[INFO] 开始调用小红书 MCP 服务
[INFO] 连接到 MCP 服务: http://localhost:18060/mcp
[INFO] MCP 会话初始化成功
[INFO] 准备调用 search_feeds 工具...
[INFO] 收到响应内容长度: 45678
[INFO] 搜索成功，找到 20 条笔记
[INFO] MCP 服务返回 20 条数据
[INFO] 正在处理第 1/20 条笔记
[INFO] 票务分析结果: {"is_ticket_resale": true, ...}
...
[INFO] 搜索完成，共处理 20 条数据
```

日志文件位置：`log/tickethunter.log`

