#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xiaohongshu-mcp 客户端封装
使用直接 HTTP 请求方式连接到本地 MCP 服务
"""

import json
import logging
from typing import List, Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)


class XiaohongshuMCPClient:
    """小红书 MCP 客户端 - 使用直接 HTTP 请求"""
    
    def __init__(self, mcp_url: str = "http://localhost:18060/mcp"):
        """
        初始化 MCP 客户端
        
        Args:
            mcp_url: MCP 服务的 URL
        """
        self.mcp_url = mcp_url
        self.session = requests.Session()
        self.session_id: Optional[str] = None
        self._request_id = 0
        
    def __enter__(self):
        """同步上下文管理器入口"""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """同步上下文管理器出口"""
        self.disconnect()
        
    def connect(self):
        """连接到 MCP 服务并初始化会话"""
        logger.info(f"连接到 MCP 服务: {self.mcp_url}")
        
        try:
            # 初始化 MCP 会话
            self._request_id += 1
            init_payload = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "tickethunter",
                        "version": "1.0.0"
                    }
                }
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            }
            
            response = self.session.post(
                self.mcp_url,
                json=init_payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            # 获取会话 ID
            self.session_id = response.headers.get('Mcp-Session-Id')
            
            result = response.json()
            if 'error' in result:
                raise RuntimeError(f"MCP 初始化失败: {result['error']}")
            
            logger.info(f"MCP 会话初始化成功，会话 ID: {self.session_id}")
                
        except Exception as e:
            logger.error(f"连接 MCP 服务失败: {str(e)}")
            raise
            
    def disconnect(self):
        """断开 MCP 连接"""
        if self.session:
            self.session.close()
            self.session = None
            logger.info("MCP 会话已关闭")
            
    def search_feeds(
        self,
        keyword: str,
        location: str = "不限",
        note_type: str = "图文",
        publish_time: str = "不限",
        search_scope: str = "未看过",
        sort_by: str = "最新"
    ) -> List[Dict[str, Any]]:
        """
        搜索小红书内容
        
        Args:
            keyword: 搜索关键词（必填）
            location: 位置距离: 不限|同城|附近
            note_type: 笔记类型: 不限|视频|图文
            publish_time: 发布时间: 不限|一天内|一周内|半年内
            search_scope: 搜索范围: 不限|已看过|未看过|已关注
            sort_by: 排序方式，默认"最新"
            
        Returns:
            笔记列表（feeds 格式）
        """
        if not self.session:
            raise RuntimeError("MCP 会话未初始化，请先调用 connect()")
            
        logger.info(f"搜索小红书内容，关键词: {keyword}")
        
        try:
            # 构建请求
            self._request_id += 1
            tool_payload = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": "tools/call",
                "params": {
                    "name": "search_feeds",
                    "arguments": {
                        "keyword": keyword,
                        "filters": {
                            "location": location,
                            "note_type": note_type,
                            "publish_time": publish_time,
                            "search_scope": search_scope,
                            "sort_by": sort_by
                        }
                    },
                    "_meta": {
                        "progressToken": self._request_id
                    }
                }
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            }
            if self.session_id:
                headers['Mcp-Session-Id'] = self.session_id
            
            # 发送请求
            logger.info("准备调用 search_feeds 工具...")
            response = self.session.post(
                self.mcp_url,
                json=tool_payload,
                headers=headers,
                timeout=120  # 2分钟超时
            )
            response.raise_for_status()
            
            # 解析响应
            result_data = response.json()
            
            if 'error' in result_data:
                error_msg = result_data['error'].get('message', '未知错误')
                raise RuntimeError(f"MCP 工具调用失败: {error_msg}")
            
            if 'result' not in result_data:
                logger.warning("响应中没有 result 字段")
                return []
            
            result = result_data['result']
            
            # 解析 result.content[0].text
            if isinstance(result, dict) and 'content' in result:
                content_list = result['content']
                if content_list and len(content_list) > 0:
                    text_content = content_list[0].get('text', '')
                    logger.info(f"收到响应内容长度: {len(text_content)}")
                    
                    # 解析 JSON
                    response_data = json.loads(text_content)
                    
                    # xiaohongshu-mcp 返回格式：{"feeds": [...], "count": N}
                    if isinstance(response_data, dict) and 'feeds' in response_data:
                        feeds = response_data['feeds']
                        logger.info(f"搜索成功，找到 {len(feeds)} 条笔记")
                        return feeds
                    elif isinstance(response_data, list):
                        logger.info(f"搜索成功，找到 {len(response_data)} 条笔记")
                        return response_data
                    else:
                        logger.warning(f"返回数据格式不符合预期: {type(response_data)}")
                        return []
            
            logger.warning("工具调用返回空结果")
            return []
                
        except json.JSONDecodeError as e:
            logger.error(f"解析 JSON 失败: {str(e)}")
            return []
        except requests.RequestException as e:
            logger.error(f"HTTP 请求失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            raise


# 便捷函数，用于快速搜索
def search_xiaohongshu(
    keyword: str,
    mcp_url: str = "http://localhost:18060/mcp",
    **filters
) -> List[Dict[str, Any]]:
    """
    快速搜索小红书内容（便捷函数）
    
    Args:
        keyword: 搜索关键词
        mcp_url: MCP 服务地址
        **filters: 其他过滤参数（location, note_type, publish_time, search_scope, sort_by）
        
    Returns:
        笔记列表（feeds 格式）
    """
    with XiaohongshuMCPClient(mcp_url) as client:
        return client.search_feeds(keyword, **filters)

