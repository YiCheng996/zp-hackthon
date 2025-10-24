#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试关键词优化功能
"""

import sys
import requests
import json
from prompts import get_keyword_optimization_prompt

# 智谱 API 配置
ZHIPU_API_KEY = 'be4d3127355e4363a4fc8fdab68e1b87.IXrJwhSFGyj47Bhu'


def optimize_keyword(original_keyword):
    """测试关键词优化"""
    print(f"\n{'='*60}")
    print(f"原始关键词: {original_keyword}")
    print(f"{'='*60}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ZHIPU_API_KEY}"
    }
    
    # 使用统一的提示词配置
    prompt = get_keyword_optimization_prompt(original_keyword)

    payload = {
        "model": "glm-4-flash",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "stream": False
    }

    try:
        response = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            print(f"❌ API 调用失败: {response.status_code}")
            print(response.text)
            return None

        result = response.json()
        optimized_keyword = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        
        print(f"\n✅ 优化后关键词: {optimized_keyword}")
        print(f"{'='*60}\n")
        
        return optimized_keyword
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return None


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "周杰伦演唱会有票转让吗",
        "求一张北京的五月天演唱会门票",
        "上海草莓音乐节的票有人要转吗？",
        "Taylor Swift演唱会",
        "想要陈奕迅演唱会的票",
        "有人转让薛之谦上海站演唱会门票吗？",
        "成都大运会门票",
        "李荣浩北京演唱会2024",
    ]
    
    print("\n" + "="*60)
    print("关键词优化测试")
    print("="*60)
    
    for keyword in test_cases:
        optimized = optimize_keyword(keyword)
        if optimized:
            if keyword != optimized:
                print(f"📝 '{keyword}' → '{optimized}'")
            else:
                print(f"✓ '{keyword}' (无需优化)")
        print()
    
    # 如果提供了命令行参数，则测试自定义关键词
    if len(sys.argv) > 1:
        custom_keyword = " ".join(sys.argv[1:])
        print("\n" + "="*60)
        print("自定义测试")
        print("="*60)
        optimize_keyword(custom_keyword)

