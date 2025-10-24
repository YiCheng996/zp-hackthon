#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""手动初始化数据库"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

def init_database():
    """初始化数据库"""
    with app.app_context():
        print("🗄️  开始初始化数据库...")
        
        # 删除所有表
        db.drop_all()
        print("✅ 已删除旧表")
        
        # 创建所有表
        db.create_all()
        print("✅ 已创建新表")
        
        # 验证表
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"\n📋 数据库表列表 ({len(tables)} 个):")
        for table in tables:
            columns = inspector.get_columns(table)
            print(f"  - {table} ({len(columns)} 列)")
        
        print("\n✨ 数据库初始化完成！")

if __name__ == '__main__':
    init_database()

