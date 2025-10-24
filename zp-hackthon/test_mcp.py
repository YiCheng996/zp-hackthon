#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接使用 HTTP 请求测试，模拟 MCP Inspector 的行为
"""

import requests
import json

MCP_URL = "http://localhost:18060/mcp"

def test_direct():
    """直接 HTTP 测试"""
    print("="*60)
    print("直接 HTTP 请求测试")
    print("="*60 + "\n")
    
    # 创建会话保持 cookie
    session = requests.Session()
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream'
    }
    
    # 步骤 1: Initialize
    print("步骤 1: 初始化会话...")
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    response = session.post(MCP_URL, json=init_payload, headers=headers, timeout=30)
    print(f"响应状态: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 初始化成功")
        print(f"会话 ID: {response.headers.get('Mcp-Session-Id', 'N/A')}")
        print(f"服务器信息: {json.dumps(data.get('result', {}), ensure_ascii=False, indent=2)}")
        
        # 保存会话 ID
        session_id = response.headers.get('Mcp-Session-Id')
        if session_id:
            headers['Mcp-Session-Id'] = session_id
    else:
        print(f"❌ 初始化失败: {response.text}")
        return False
    
    # 步骤 2: 调用工具
    print("\n步骤 2: 调用 search_feeds 工具...")
    tool_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search_feeds",
            "arguments": {
                "keyword": "周杰伦",
                "filters": {
                    "sort_by": "最新"
                }
            },
            "_meta": {
                "progressToken": 2
            }
        }
    }
    
    print("发送请求...")
    print(f"URL: {MCP_URL}")
    print(f"Payload: {json.dumps(tool_payload, ensure_ascii=False, indent=2)}")
    
    try:
        response = session.post(
            MCP_URL,
            json=tool_payload,
            headers=headers,
            timeout=120,  # 2分钟超时
            stream=False  # 先不用流式
        )
        
        print(f"\n响应状态: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        
        if response.status_code == 200:
            result_data = response.json()
            
            if 'result' in result_data:
                result = result_data['result']
                print(f"\n✅ 调用成功!")
                
                if isinstance(result, dict) and 'content' in result:
                    content = result['content']
                    if content and len(content) > 0:
                        text = content[0].get('text', '')
                        print(f"收到文本长度: {len(text)}")
                        
                        # 解析 JSON
                        data = json.loads(text)
                        if 'feeds' in data:
                            feeds = data['feeds']
                            print(f"\n找到 {len(feeds)} 条笔记")
                            
                            if len(feeds) > 0:
                                print("\n第一条笔记:")
                                first = feeds[0]
                                print(f"  - ID: {first.get('id')}")
                                print(f"  - 标题: {first.get('noteCard', {}).get('displayTitle', 'N/A')}")
                                print(f"  - 作者: {first.get('noteCard', {}).get('user', {}).get('nickname', 'N/A')}")
                            
                            return True
                print(json.dumps(result, ensure_ascii=False, indent=2)[:500])
            elif 'error' in result_data:
                print(f"\n❌ 错误: {result_data['error']}")
            else:
                print(f"\n⚠️  未知响应格式: {result_data}")
        else:
            print(f"❌ 请求失败: {response.text}")
        
        return False
        
    except requests.Timeout:
        print("\n❌ 请求超时（2分钟）")
        return False
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        result = test_direct()
        print("\n" + "="*60)
        if result:
            print("✅ 测试成功")
        else:
            print("❌ 测试失败")
        print("="*60)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被中断")

