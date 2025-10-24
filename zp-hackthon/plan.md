### 改造计划：将小红书数据获取迁移至本地 MCP 服务

**目标:** 将项目中通过 COZE API 获取小红书笔记的方式，替换为调用本地部署的 `xiaohongshu-mcp` 服务。

**前置条件:**
*   `xiaohongshu-mcp` 服务已在本地 `http://localhost:18060/mcp` 成功部署并运行。

**改造步骤:**

---

#### **第一步：更新项目配置 (`config.py`)**

1.  **移除旧配置**: 删除不再需要的 COZE API 和小红书 Cookie 相关配置项，因为 MCP 服务会自己管理认证。
    *   `COZE_API_KEY`
    *   `COZE_WORKFLOW_ID`
    *   `XIAOHONGSHU_COOKIE`
    *   `XIAOHONGSHU_COOKIE_UPDATE_TIME`
    *   `XIAOHONGSHU_COOKIE_EXPIRE_DAYS`

2.  **添加新配置**: 新增 MCP 服务的 URL 配置，方便后续在代码中统一调用和管理。
    ```python
    # 小红书 MCP 服务配置
    MCP_XIAOHONGSHU_URL = 'http://localhost:18060/mcp'
    ```

---

#### **第二步：修改核心业务逻辑 (`app.py`)**

1.  **定位修改点**: 找到 `execute_search_task` 函数，这是当前执行搜索任务和获取数据的核心入口。

2.  **替换数据源**:
    *   删除函数内调用 `https://api.coze.cn/v1/workflow/run` 的 `requests.post` 相关代码块。
    *   移除检查 Cookie 是否过期的逻辑。
    *   新增调用本地 `xiaohongshu-mcp` 服务的代码。
    *   **重要假设**: 我们需要确认 `xiaohongshu-mcp` 服务的具体 API 调用方式。根据项目实践，我们**初步假设**其提供了一个用于搜索的 `GET` 接口，例如 `/search`，并通过 `keyword` 参数传递搜索词。

3.  **实现代码（伪代码示例）**:
    ```python
    # ... 在 execute_search_task 函数内部 ...
    try:
        mcp_base_url = app.config['MCP_XIAOHONGSHU_URL']
        # 假设的搜索端点，需要根据 mcp 服务的实际情况进行最终确认
        search_url = f"{mcp_base_url}/search" 
        params = {"keyword": keyword}
        
        app.logger.info(f"开始调用小红书 MCP 服务，URL: {search_url}，关键词: {keyword}")
        response = requests.get(search_url, params=params, timeout=120)
        response.raise_for_status() # 如果请求失败 (非2xx状态码)，将抛出异常
        response_data = response.json()
        app.logger.info(f"MCP 服务响应成功")
        
        # ... 后续的数据处理逻辑 ...
        
    except requests.exceptions.RequestException as e:
        logger.error(f"调用 MCP 服务失败: {str(e)}")
        # ... 相应的错误处理逻辑 ...
    ```

4.  **适配数据结构**:
    *   我们需要分析 `xiaohongshu-mcp` 服务返回的 JSON 数据结构。
    *   然后，修改后续处理笔记列表（`notes_data`）的代码，以确保能够正确解析新接口返回的字段（例如：`note_id`, `note_desc`, `note_url`, `note_create_time` 等）。
    *   **初步假设**: 为了尽可能减少改动，我们会假设新接口返回的数据结构与原 COZE API 的核心字段保持一致或类似。

---

#### **第三步：清理和文档更新 (`Readme.md`)**

1.  **更新文档**:
    *   修改 `Readme.md` 中的“配置API密钥”部分，移除关于 `COZE_API_KEY` 和 `XIAOHONGSHU_COOKIE` 的说明。
    *   新增关于如何部署和配置 `xiaohongshu-mcp` 服务作为项目前置条件的说明，并指导用户在 `config.py` 中配置 `MCP_XIAOHONGSHU_URL`。

---

**总结:**
此计划将分三步，从 **配置** -> **核心代码** -> **文档** 对项目进行改造。关键点在于**确认 `xiaohongshu-mcp` 服务的确切API接口和返回的数据结构**，这是第二步能否顺利实施的核心。

如果您确认此计划可行，我就可以开始进行代码的实际修改。

