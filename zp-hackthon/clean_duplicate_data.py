#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理数据库中的重复数据
"""

from app import app
from database import db, Note, Ticket
from sqlalchemy import func

def clean_duplicate_tickets():
    """清理重复的票务信息"""
    with app.app_context():
        print("\n" + "="*60)
        print("清理重复票务数据")
        print("="*60)
        
        # 查找重复的票务信息（同一个 note_id 有多条 ticket）
        duplicate_notes = db.session.query(
            Ticket.note_id,
            func.count(Ticket.id).label('count')
        ).group_by(Ticket.note_id).having(func.count(Ticket.id) > 1).all()
        
        if not duplicate_notes:
            print("✅ 没有发现重复的票务数据")
            return
        
        print(f"发现 {len(duplicate_notes)} 个笔记有重复票务信息：")
        
        total_deleted = 0
        for note_id, count in duplicate_notes:
            print(f"\n笔记 ID: {note_id}, 重复数量: {count}")
            
            # 获取该笔记的所有票务信息
            tickets = Ticket.query.filter_by(note_id=note_id).order_by(Ticket.created_at.asc()).all()
            
            # 保留第一条，删除其他的
            keep_ticket = tickets[0]
            print(f"  保留: ID={keep_ticket.id}, 演出={keep_ticket.event_name}, 创建时间={keep_ticket.created_at}")
            
            for ticket in tickets[1:]:
                print(f"  删除: ID={ticket.id}, 演出={ticket.event_name}, 创建时间={ticket.created_at}")
                db.session.delete(ticket)
                total_deleted += 1
        
        db.session.commit()
        print(f"\n✅ 清理完成！共删除 {total_deleted} 条重复数据")


def show_database_stats():
    """显示数据库统计信息"""
    with app.app_context():
        print("\n" + "="*60)
        print("数据库统计信息")
        print("="*60)
        
        note_count = Note.query.count()
        ticket_count = Ticket.query.count()
        
        print(f"笔记总数: {note_count}")
        print(f"票务总数: {ticket_count}")
        
        # 查找有多个票务的笔记
        duplicate_notes = db.session.query(
            Ticket.note_id,
            func.count(Ticket.id).label('count')
        ).group_by(Ticket.note_id).having(func.count(Ticket.id) > 1).all()
        
        if duplicate_notes:
            print(f"\n⚠️  有重复票务的笔记: {len(duplicate_notes)}")
        else:
            print(f"\n✅ 没有重复票务")
        
        # 显示最近的票务信息
        print(f"\n最近 5 条票务信息:")
        recent_tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(5).all()
        for i, ticket in enumerate(recent_tickets, 1):
            print(f"  {i}. {ticket.event_name} - {ticket.city} (ID: {ticket.id}, Note ID: {ticket.note_id})")


def clear_all_data():
    """清空所有数据（危险操作）"""
    with app.app_context():
        print("\n" + "="*60)
        print("⚠️  清空所有数据")
        print("="*60)
        
        confirm = input("确认要删除所有数据吗？输入 'YES' 确认: ")
        if confirm != 'YES':
            print("已取消")
            return
        
        ticket_count = Ticket.query.count()
        note_count = Note.query.count()
        
        Ticket.query.delete()
        Note.query.delete()
        db.session.commit()
        
        print(f"✅ 已删除 {ticket_count} 条票务信息和 {note_count} 条笔记")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "clean":
            clean_duplicate_tickets()
            show_database_stats()
        elif command == "stats":
            show_database_stats()
        elif command == "clear":
            clear_all_data()
        else:
            print(f"未知命令: {command}")
            print("可用命令:")
            print("  clean  - 清理重复数据")
            print("  stats  - 显示统计信息")
            print("  clear  - 清空所有数据")
    else:
        print("数据库清理工具")
        print("="*60)
        print("使用方法:")
        print("  python clean_duplicate_data.py clean  - 清理重复数据")
        print("  python clean_duplicate_data.py stats  - 显示统计信息")
        print("  python clean_duplicate_data.py clear  - 清空所有数据")
        print()
        show_database_stats()

