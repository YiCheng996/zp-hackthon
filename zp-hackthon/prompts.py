#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 提示词配置文件
统一管理所有大模型提示词
"""


class Prompts:
    """AI 提示词配置类"""
    
    # 关键词优化提示词
    KEYWORD_OPTIMIZATION = """你是一个小红书搜索关键词优化助手。用户想在小红书上搜索演唱会、音乐会等演出的转让票务信息。

请分析用户输入的关键词，理解用户意图，并优化为最适合在小红书上搜索票务转让信息的关键词。

优化规则：
1. 提取核心演出名称、艺人/乐队名称
2. 去除冗余词汇（如"的票"、"求票"、"有人转让吗"等）
3. 保留关键的时间、地点信息（如城市名）
4. 如果是明星演唱会，保留明星名字
5. 如果是音乐节/展览，保留活动名称
6. 简洁明了，便于搜索

用户输入: {keyword}

请直接返回优化后的关键词，不要有任何解释说明。如果原关键词已经很好，可以直接返回。

优化后的关键词:"""

    # 票务信息识别提示词
    TICKET_ANALYSIS = """你是一个票务信息分析助手。请分析以下小红书笔记内容，判断对方是否有销售商品、演唱会门票的意向，并提取相关信息。

笔记内容：
{content}

请按照以下JSON格式返回结果（只返回JSON，不要其他说明）：

{{
    "is_ticket_resale": true/false,  // 是否为票务转让
    "event_name": "演出名称",
    "city": "城市",
    "event_date": "YYYY-MM-DD",  // 演出日期，格式为YYYY-MM-DD，若原文未给出，默认年份为2025年
    "area": "座位区域",
    "price": "价格",
    "quantity": "数量",
    "contact": "联系方式",
    "notes": "其他备注"
}}

判断规则：
1. 包含"转让"、"出"、"求"等关键词
2. 提到演出/演唱会名称
3. 包含价格信息
4. 如果不是票务转让信息，is_ticket_resale 设为 false，其他字段可为空字符串

请分析："""

    @classmethod
    def get_keyword_optimization_prompt(cls, keyword: str) -> str:
        """
        获取关键词优化提示词
        
        Args:
            keyword: 用户输入的原始关键词
            
        Returns:
            格式化后的提示词
        """
        return cls.KEYWORD_OPTIMIZATION.format(keyword=keyword)
    
    @classmethod
    def get_ticket_analysis_prompt(cls, content: str) -> str:
        """
        获取票务信息分析提示词
        
        Args:
            content: 笔记内容
            
        Returns:
            格式化后的提示词
        """
        return cls.TICKET_ANALYSIS.format(content=content)


# 导出便捷函数
def get_keyword_optimization_prompt(keyword: str) -> str:
    """获取关键词优化提示词"""
    return Prompts.get_keyword_optimization_prompt(keyword)


def get_ticket_analysis_prompt(content: str) -> str:
    """获取票务信息分析提示词"""
    return Prompts.get_ticket_analysis_prompt(content)

