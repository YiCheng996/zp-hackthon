# TicketHunter 迁移总结

## 迁移概述

成功将 TicketHunter 项目从 COZE API 迁移到本地 xiaohongshu-mcp 服务。

## 完成的工作

### 1. ✅ MCP 服务验证
- 确认本地 xiaohongshu-mcp 服务可用
- 验证搜索接口正常工作
- 测试数据返回格式

### 2. ✅ 客户端实现
- 创建 `mcp_client.py` 
- 使用直接 HTTP 请求方式（已验证稳定）
- 实现完整的会话管理和错误处理
- 支持同步调用方式

### 3. ✅ 配置更新
**文件**: `config.py`
- 移除：`COZE_API_KEY`、`COZE_WORKFLOW_ID`
- 移除：`XIAOHONGSHU_COOKIE*` 相关配置
- 新增：`MCP_XIAOHONGSHU_URL = 'http://localhost:18060/mcp'`

### 4. ✅ 核心逻辑改造
**文件**: `app.py`
- 导入 `XiaohongshuMCPClient`
- 重写 `execute_search_task` 函数
- 适配 MCP 返回的 feeds 数据结构
- 保持原有的票务分析和通知逻辑

### 5. ✅ 数据结构适配
**MCP返回格式**:
```json
{
  "feeds": [
    {
      "id": "笔记ID",
      "modelType": "note",
      "noteCard": {
        "displayTitle": "标题",
        "user": {...},
        "interactInfo": {...}
      }
    }
  ],
  "count": 21
}
```

**适配逻辑**:
- 过滤非笔记类型（hot_query等）
- 提取 feed.id 作为 note_id
- 使用 noteCard.displayTitle 作为描述
- 构建标准小红书 URL

### 6. ✅ 文档更新
- 更新 `README.md`
  - 添加 xiaohongshu-mcp 服务部署说明
  - 更新配置步骤
  - 新增 MCP 服务相关的常见问题
- `requirements.txt` 保持不变（已包含必要依赖）

### 7. ✅ 测试脚本
- 保留 `test_mcp.py`（直接 HTTP 测试）
- 删除其他无用测试文件
- 测试脚本可独立验证 MCP 服务

## 技术要点

### 为什么使用直接 HTTP 而非 MCP SDK？
在测试中发现，使用 MCP Python SDK 的 `ClientSession` 在调用 `call_tool` 时会卡住，可能是与 xiaohongshu-mcp 的 HTTP 实现不完全兼容。

直接 HTTP 请求方式：
- ✅ 已验证稳定可靠
- ✅ 代码更简洁
- ✅ 易于调试
- ✅ 无异步复杂性

### MCP 调用流程
1. POST `/mcp` - 初始化会话 (`method: "initialize"`)
2. 获取 `Mcp-Session-Id` 响应头
3. POST `/mcp` - 调用工具 (`method: "tools/call"`)
   - 携带 `Mcp-Session-Id` 头
   - 参数包含 `_meta.progressToken`
4. 解析响应中的 `result.content[0].text` JSON

### 关键代码改动

**旧代码** (COZE API):
```python
url = "https://api.coze.cn/v1/workflow/run"
response = requests.post(url, headers=headers, json=data)
content_data = json.loads(response_data['data'])
notes_data = content_data.get('output', [])
for note_item in notes_data:
    note_data = note_item['note']
```

**新代码** (MCP):
```python
with XiaohongshuMCPClient(app.config['MCP_XIAOHONGSHU_URL']) as client:
    feeds = client.search_feeds(keyword, sort_by="最新")
for feed in feeds:
    if feed.get('modelType') != 'note':
        continue
    feed_id = feed.get('id')
    note_card = feed.get('noteCard', {})
```

## 使用指南

### 前置条件
1. 部署并启动 xiaohongshu-mcp 服务
2. 确保服务运行在 `http://localhost:18060/mcp`
3. 完成小红书登录认证

### 测试 MCP 服务
```bash
python test_mcp.py
```

### 启动应用
```bash
python app.py
```

## 注意事项

1. **MCP 服务依赖**：应用启动前必须确保 xiaohongshu-mcp 服务已运行
2. **登录状态**：xiaohongshu-mcp 需要完成小红书登录才能搜索
3. **数据格式**：MCP 返回的 displayTitle 可能较短，不如原 COZE API 的 note_desc 详细
4. **性能**：首次搜索可能需要 30-60 秒（MCP 服务爬取数据）

## 文件清单

### 新增文件
- `mcp_client.py` - MCP 客户端封装
- `test_mcp.py` - MCP 服务测试脚本
- `MIGRATION_SUMMARY.md` - 本文档

### 修改文件
- `config.py` - 更新配置
- `app.py` - 重写搜索逻辑
- `README.md` - 更新文档

### 删除文件
- `test_mcp_sdk.py`
- `test_mcp_search.py`
- `test_mcp_quick.py`
- `test_mcp_simple.py`
- `test_mcp_client.py`
- `test_mcp_debug.py`
- `mcp.py` (冲突文件)

## 后续建议

1. **数据增强**：考虑从 MCP 返回的更多字段中提取信息
2. **错误恢复**：添加 MCP 服务重连机制
3. **缓存优化**：对 MCP 搜索结果进行缓存
4. **监控告警**：添加 MCP 服务健康检查

## 迁移完成 ✅

所有计划中的步骤均已完成，项目已成功迁移到 xiaohongshu-mcp 服务！

