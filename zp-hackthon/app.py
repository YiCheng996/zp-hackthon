"""
TicketHunter - 票务监控系统

业务流程：
1. 用户搜索流程
   - 用户输入关键词进行搜索
   - 系统创建搜索任务并记录到数据库
   - 调用COZE API获取小红书笔记列表
   - 使用通义千问AI分析笔记内容，提取票务信息
   - 实时推送分析结果到前端展示

2. 数据处理流程
   - 解析API返回的笔记数据
   - 过滤已存在的笔记，避免重复处理
   - 使用AI模型分析笔记内容，识别票务信息
   - 将票务信息保存到数据库
   - 通过SSE推送新数据到前端

3. 实时通信机制
   - 使用Server-Sent Events (SSE)实现服务器推送
   - 支持任务状态实时更新
   - 支持票务信息实时展示
   - 自动重连机制确保连接稳定


主要组件：
1. Monitor类：负责任务管理和监控
2. 数据模型：Note（笔记）和Ticket（票务）
3. WorkflowExecution：任务执行记录
4. EventQueue：实时消息队列

技术栈：
- Flask：Web框架
- SQLite：数据存储
- 智谱AI：AI分析
- SSE：实时通信
- Bootstrap：前端UI
"""

import os
import sys
import socket
import platform
import subprocess
import time
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
import requests
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import re
from flask_login import LoginManager, UserMixin, login_required
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from logging.handlers import RotatingFileHandler
from database import db, Note, Ticket, WorkflowExecution, init_db
from queue import Queue, Empty
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
# 智谱AI API
import sseclient
# 小红书 MCP 客户端
from mcp_client import XiaohongshuMCPClient
# AI 提示词配置
from prompts import get_keyword_optimization_prompt, get_ticket_analysis_prompt

# 创建数据库写入锁
db_lock = Lock()

# 创建事件队列
event_queue = Queue()

# 创建扩展对象
cache = Cache()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)

# 配置日志
def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler('log/tickethunter.log', maxBytes=1024*1024, backupCount=5, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    app.config.from_object('config.Config')
    
    # 初始化各种扩展
    db.init_app(app)
    cache.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    
    return app

# 创建应用实例
app = create_app()

def _create_zhipu_client(stream_response):
    """将流式响应包装为可迭代对象"""
    return sseclient.SSEClient(stream_response)

# 监控类
class Monitor:
    def __init__(self):
        self.keywords = set()
        self.is_running = False
        self.scheduler = BackgroundScheduler()
        self.task_jobs = {}  # 存储任务ID到job_id的映射

        
    def start(self):
        """启动监控"""
        if not self.is_running:
            self.is_running = True
            # 启动调度器
            self.scheduler.start()
            # 恢复所有启用定时任务的工作流
            with app.app_context():
                active_tasks = WorkflowExecution.query.filter_by(
                    is_scheduled=True,
                    status='running'
                ).all()
                for task in active_tasks:
                    self.add_task_schedule(task.id, task.msg, task.schedule_interval)
            app.logger.info("监控服务已启动")
            
    def stop(self):
        """停止监控"""
        if self.is_running:
            self.is_running = False
            self.scheduler.shutdown()
            app.logger.info("监控服务已停止")
            
    def add_keyword(self, keyword):
        """添加监控关键词（兼容旧接口）"""
        self.keywords.add(keyword)
        app.logger.info(f"已添加监控关键词: {keyword}")
        
    def remove_keyword(self, keyword):
        """移除监控关键词（兼容旧接口）"""
        if keyword in self.keywords:
            self.keywords.remove(keyword)
            app.logger.info(f"已移除监控关键词: {keyword}")
    
    def add_task_schedule(self, task_id, keyword, interval_seconds=60):
        """为任务添加定时执行"""
        job_id = f"task_{task_id}"
        
        # 如果任务已存在，先移除
        if job_id in self.task_jobs:
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass
        
        # 添加新的定时任务
        self.scheduler.add_job(
            execute_scheduled_task,
            'interval',
            seconds=interval_seconds,
            id=job_id,
            args=[task_id, keyword],
            replace_existing=True
        )
        
        self.task_jobs[task_id] = job_id
        
        # 更新下次执行时间
        with app.app_context():
            task = WorkflowExecution.query.get(task_id)
            if task:
                task.next_run_at = datetime.utcnow() + timedelta(seconds=interval_seconds)
                db.session.commit()
        
        app.logger.info(f"已为任务 {task_id} ({keyword}) 添加定时任务，间隔 {interval_seconds} 秒")
    
    def pause_task_schedule(self, task_id):
        """暂停任务定时执行"""
        job_id = f"task_{task_id}"
        
        if job_id in self.task_jobs:
            try:
                self.scheduler.pause_job(job_id)
                app.logger.info(f"已暂停任务 {task_id} 的定时执行")
                
                # 更新数据库状态
                with app.app_context():
                    task = WorkflowExecution.query.get(task_id)
                    if task:
                        task.status = 'paused'
                        db.session.commit()
                return True
            except Exception as e:
                app.logger.error(f"暂停任务失败: {str(e)}")
                return False
        return False
    
    def resume_task_schedule(self, task_id):
        """恢复任务定时执行"""
        job_id = f"task_{task_id}"
        
        if job_id in self.task_jobs:
            try:
                self.scheduler.resume_job(job_id)
                app.logger.info(f"已恢复任务 {task_id} 的定时执行")
                
                # 更新数据库状态
                with app.app_context():
                    task = WorkflowExecution.query.get(task_id)
                    if task:
                        task.status = 'running'
                        db.session.commit()
                return True
            except Exception as e:
                app.logger.error(f"恢复任务失败: {str(e)}")
                return False
        return False
            
    def remove_task_schedule(self, task_id):
        """移除任务定时执行"""
        job_id = f"task_{task_id}"
        
        if job_id in self.task_jobs:
            try:
                self.scheduler.remove_job(job_id)
                del self.task_jobs[task_id]
                app.logger.info(f"已移除任务 {task_id} 的定时任务")
                
                # 更新数据库状态
                with app.app_context():
                    task = WorkflowExecution.query.get(task_id)
                    if task:
                        task.is_scheduled = False
                        task.status = 'stopped'
                        db.session.commit()
                return True
            except Exception as e:
                app.logger.error(f"移除任务失败: {str(e)}")
                return False
        return False

# 创建监控实例
monitor = Monitor()

def execute_scheduled_task(task_id, keyword):
    """定时执行任务"""
    app.logger.info(f"定时任务触发: 任务ID={task_id}, 关键词={keyword}")
    
    with app.app_context():
        # 获取任务
        task = WorkflowExecution.query.get(task_id)
        if not task:
            app.logger.error(f"任务不存在: {task_id}")
            return
        
        # 检查任务状态
        if task.status not in ['running', 'paused']:
            app.logger.info(f"任务状态为 {task.status}，跳过执行")
            return
        
        if task.status == 'paused':
            app.logger.info(f"任务已暂停，跳过执行")
            return
        
        # 更新执行信息
        task.last_run_at = datetime.utcnow()
        task.run_count = (task.run_count or 0) + 1
        task.next_run_at = datetime.utcnow() + timedelta(seconds=task.schedule_interval)
        task.message = f"第 {task.run_count} 次定时执行"
        db.session.commit()
        
        # 通知前端任务状态更新
        notify_clients('task_update', {
            'task_id': task_id,
            'status': 'running',
            'message': task.message,
            'run_count': task.run_count,
            'last_run_at': task.last_run_at.isoformat() if task.last_run_at else None,
            'next_run_at': task.next_run_at.isoformat() if task.next_run_at else None
        })
        
        # 执行搜索
        app.logger.info(f"开始执行定时搜索，关键词: {keyword}")
        
        try:
            # 优化关键词
            optimized_keyword = optimize_search_keyword(keyword)
            app.logger.info(f"优化后的关键词: {optimized_keyword}")
            
            # 通知前端
            notify_clients('task_update', {
                'task_id': task_id,
                'status': 'running',
                'message': f'正在搜索小红书内容（{optimized_keyword}）...'
            })
            
            # 调用小红书MCP服务
            with XiaohongshuMCPClient(app.config['MCP_XIAOHONGSHU_URL']) as client:
                feeds = client.search_feeds(optimized_keyword, sort_by="最新")
            
            app.logger.info(f"定时任务搜索成功，找到 {len(feeds)} 条笔记")
            
            # 通知前端
            notify_clients('task_update', {
                'task_id': task_id,
                'status': 'running',
                'message': f'找到 {len(feeds)} 条笔记，正在分析...'
            })
            
            # 并发处理笔记
            ticket_count = 0
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_feed = {
                    executor.submit(process_single_feed, feed, task_id): feed 
                    for feed in feeds
                }
                
                for future in as_completed(future_to_feed):
                    try:
                        result = future.result()
                        if result['success'] and result.get('is_ticket'):
                            ticket_count += 1
                            app.logger.info(f"发现新票务: {result.get('event_name')}")
                    except Exception as e:
                        app.logger.error(f"处理笔记失败: {str(e)}")
            
            # 更新任务消息
            task.message = f"第 {task.run_count} 次执行完成，发现 {ticket_count} 条新票务"
            db.session.commit()
            
            # 通知前端
            notify_clients('task_update', {
                'task_id': task_id,
                'status': 'running',
                'message': task.message
            })
            
            app.logger.info(f"定时任务执行完成: 任务ID={task_id}, 新票务={ticket_count}")
            
        except Exception as e:
            app.logger.error(f"定时任务执行失败: {str(e)}")
            task.message = f"执行失败: {str(e)}"
            db.session.commit()
            
            notify_clients('task_update', {
                'task_id': task_id,
                'status': 'running',
                'message': task.message
            })

def analyze_ticket_content(note_desc):
    """使用智谱AI分析笔记内容中的票务信息"""
    app.logger.info(f"开始分析笔记内容: {note_desc}")
    
    # 使用统一的提示词配置
    prompt = get_ticket_analysis_prompt(note_desc)
    
    try:
        app.logger.info("开始调用智谱AI API")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {app.config['ZHIPU_API_KEY']}"
        }
        payload = {
            "model": "glm-4-flash",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "stream": True
        }

        response = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=60
        )

        if response.status_code != 200:
            app.logger.error(f"智谱AI API调用失败: {response.status_code}, {response.text}")
            return {"is_ticket_resale": False}

        sse_client = _create_zhipu_client(response)
        full_text = ""
        for event in sse_client.events():
            if event.data:
                try:
                    event_data = json.loads(event.data)
                except json.JSONDecodeError:
                    continue

                delta = event_data.get("choices", [{}])[0].get("delta", {})
                if isinstance(delta, dict) and "content" in delta:
                    full_text += delta["content"]

        app.logger.info(f"智谱AI API响应: {full_text}")

        try:
            json_start = full_text.find('{')
            json_end = full_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = full_text[json_start:json_end]
                result = json.loads(json_str)
                app.logger.info(f"解析票务信息结果: {json.dumps(result, ensure_ascii=False)}")
                return result
            else:
                app.logger.error("未找到JSON数据")
                return {"is_ticket_resale": False}
        except json.JSONDecodeError as e:
            app.logger.error(f"解析JSON失败: {str(e)}, 原文: {full_text}")
            return {"is_ticket_resale": False}
            
    except Exception as e:
        app.logger.error(f"调用AI服务出错: {str(e)}")
        return {"is_ticket_resale": False}


def optimize_search_keyword(original_keyword):
    """
    使用大模型优化搜索关键词
    分析用户意图，提取核心搜索词
    
    Args:
        original_keyword: 原始关键词
        
    Returns:
        优化后的关键词
    """
    app.logger.info(f"开始优化搜索关键词: {original_keyword}")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {app.config['ZHIPU_API_KEY']}"
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

        response = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            app.logger.error(f"关键词优化 API 调用失败: {response.status_code}, {response.text}")
            return original_keyword

        result = response.json()
        optimized_keyword = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        
        if not optimized_keyword:
            app.logger.warning("关键词优化返回空结果，使用原始关键词")
            return original_keyword
            
        app.logger.info(f"关键词优化成功: '{original_keyword}' -> '{optimized_keyword}'")
        return optimized_keyword
        
    except Exception as e:
        app.logger.error(f"关键词优化失败: {str(e)}，使用原始关键词")
        return original_keyword


def process_single_feed(feed, workflow_execution_id):
    """
    处理单个 feed，创建笔记并分析票务信息
    
    Args:
        feed: feed 数据
        workflow_execution_id: 工作流执行 ID
        
    Returns:
        dict: 包含处理结果的字典
    """
    try:
        # 跳过非笔记类型
        if feed.get('modelType') != 'note':
            return {'success': False, 'reason': 'not_note_type'}
        
        feed_id = feed.get('id')
        note_card = feed.get('noteCard', {})
        
        if not feed_id or not note_card:
            return {'success': False, 'reason': 'incomplete_data'}
        
        # 使用锁保护数据库操作，防止并发写入冲突
        with db_lock:
            with app.app_context():
                # 再次检查笔记是否已存在（双重检查锁定模式）
                existing_note = db.session.get(Note, feed_id)
                if existing_note:
                    app.logger.info(f"笔记已存在，跳过: {feed_id}")
                    return {'success': False, 'reason': 'already_exists', 'note_id': feed_id}
                
                # 构建笔记 URL
                note_url = f"https://www.xiaohongshu.com/explore/{feed_id}"
                
                # 创建新笔记
                note = Note(
                    note_id=feed_id,
                    description=note_card.get('displayTitle', ''),
                    note_url=note_url,
                    create_time=datetime.now()
                )
                db.session.add(note)
                db.session.flush()  # 刷新，使其他事务可见
                
                app.logger.info(f"已保存笔记: {feed_id} - {note.description[:50]}")
        
        # 分析票务信息（在锁外进行，避免长时间持有锁）
        ticket_info = analyze_ticket_content(note_card.get('displayTitle', ''))
        app.logger.info(f"票务分析结果: {ticket_info.get('is_ticket_resale')} - {ticket_info.get('event_name', 'N/A')}")
        
        if ticket_info.get('is_ticket_resale'):
            # 使用锁保护票务信息写入
            with db_lock:
                with app.app_context():
                    # 检查该笔记是否已有票务信息
                    existing_ticket = Ticket.query.filter_by(note_id=feed_id).first()
                    if existing_ticket:
                        app.logger.warning(f"票务信息已存在，跳过: {feed_id}")
                        return {'success': False, 'reason': 'ticket_exists', 'note_id': feed_id}
                    
                    # 创建票务信息
                    ticket = Ticket(
                        note_id=feed_id,
                        is_ticket_resale=ticket_info.get('is_ticket_resale', True),
                        event_name=ticket_info.get('event_name', ''),
                        city=ticket_info.get('city', ''),
                        event_date=datetime.strptime(ticket_info['event_date'], '%Y-%m-%d').date()
                        if ticket_info.get('event_date') else None,
                        area=ticket_info.get('area', ''),
                        price=ticket_info.get('price', ''),
                        quantity=ticket_info.get('quantity', ''),
                        contact=ticket_info.get('contact', ''),
                        notes=ticket_info.get('notes', '')
                    )
                    db.session.add(ticket)
                    db.session.commit()
                    
                    app.logger.info(f"已保存票务: {ticket.event_name} - {ticket.city}")
                    
                    return {
                        'success': True,
                        'is_ticket': True,
                        'ticket': {
                            'event_name': ticket.event_name,
                            'city': ticket.city,
                            'event_date': ticket.event_date.strftime('%Y-%m-%d') if ticket.event_date else None,
                            'price': ticket.price,
                            'area': ticket.area,
                            'quantity': ticket.quantity,
                            'contact': ticket.contact,
                            'notes': ticket.notes,
                            'note_url': note_url
                        }
                    }
        else:
            # 提交笔记（非票务信息）
            with db_lock:
                with app.app_context():
                    db.session.commit()
            return {'success': True, 'is_ticket': False, 'note_id': feed_id}
                
    except Exception as e:
        app.logger.error(f"处理 feed 失败: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        # 回滚事务
        try:
            with app.app_context():
                db.session.rollback()
        except:
            pass
        return {'success': False, 'reason': 'error', 'error': str(e)}


def execute_search_task(keyword):
    """执行搜索任务"""
    app.logger.info(f"开始执行搜索任务，原始关键词: {keyword}")
    workflow_execution = None
    
    try:
        # 第一步：使用大模型优化搜索关键词
        optimized_keyword = optimize_search_keyword(keyword)
        app.logger.info(f"关键词优化完成: '{keyword}' -> '{optimized_keyword}'")
        
        # 保存工作流执行记录（记录优化后的关键词）
        workflow_execution = WorkflowExecution(
            code=200,
            cost=0,
            msg=f"{keyword} (优化为: {optimized_keyword})" if keyword != optimized_keyword else keyword,
            status='running',
            raw_response={},
            is_scheduled=True,  # 启用定时任务
            schedule_interval=60,  # 60秒间隔
            run_count=0,
            message="首次执行中..."
        )
        db.session.add(workflow_execution)
        db.session.commit()
        
        task_id = workflow_execution.id
        
        # 添加定时任务
        monitor.add_task_schedule(task_id, keyword, interval_seconds=60)
        
        # 通知客户端任务开始
        notify_clients('task_update', {
            'task_id': workflow_execution.id,
            'status': 'running',
            'message': f'正在搜索：{optimized_keyword}' + (f' (优化自: {keyword})' if keyword != optimized_keyword else '')
        })
        
        # 第二步：调用小红书 MCP 服务
        app.logger.info("开始调用小红书 MCP 服务")
        
        # 调用小红书 MCP 服务（使用优化后的关键词）
        try:
            with XiaohongshuMCPClient(app.config['MCP_XIAOHONGSHU_URL']) as client:
                feeds = client.search_feeds(optimized_keyword, sort_by="最新")
        except Exception as e:
            app.logger.error(f"调用 MCP 服务失败: {str(e)}")
            workflow_execution.status = 'failed'
            workflow_execution.code = 500
            db.session.commit()
            notify_clients('task_update', {
                'task_id': workflow_execution.id,
                'status': 'failed',
                'message': f'MCP 服务调用失败: {str(e)}'
            })
            return False
        
        app.logger.info(f"MCP 服务返回 {len(feeds)} 条数据")
        
        if not feeds:
            workflow_execution.status = 'completed'
            db.session.commit()
            notify_clients('task_update', {
                'task_id': workflow_execution.id,
                'status': 'completed',
                'message': '未找到相关数据'
            })
            return False
            
        total_notes = len(feeds)
        processed_notes = 0
        ticket_count = 0
        
        app.logger.info(f"开始并发处理 {total_notes} 条笔记数据（并发数：5）")
        
        # 使用线程池实现5并发处理
        with ThreadPoolExecutor(max_workers=5) as executor:
            # 提交所有任务
            future_to_feed = {
                executor.submit(process_single_feed, feed, workflow_execution.id): feed 
                for feed in feeds
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_feed):
                processed_notes += 1
                
                try:
                    result = future.result()
                    
                    if result.get('success') and result.get('is_ticket'):
                        ticket_count += 1
                        # 通知客户端新票务信息
                        notify_clients('ticket_update', {
                            'task_id': workflow_execution.id,
                            'ticket': result['ticket']
                        })
                        app.logger.info(f"发现票务信息 ({ticket_count}): {result['ticket']['event_name']}")
                    
                    # 更新任务状态，显示处理进度
                    if processed_notes % 5 == 0 or processed_notes == total_notes:
                        notify_clients('task_update', {
                            'task_id': workflow_execution.id,
                            'status': 'running',
                            'message': f'已处理 {processed_notes}/{total_notes} 条数据，发现 {ticket_count} 条票务'
                        })
                        
                except Exception as e:
                    app.logger.error(f"处理任务结果时出错: {str(e)}")
                    continue
        
        app.logger.info(f"并发处理完成，共处理 {total_notes} 条，发现 {ticket_count} 条票务信息")
        
        workflow_execution.status = 'completed'
        db.session.commit()
        notify_clients('task_update', {
            'task_id': workflow_execution.id,
            'status': 'completed',
            'message': f'搜索完成，共处理 {total_notes} 条数据，发现 {ticket_count} 条票务信息'
        })
        return True
        
    except Exception as e:
        logger.error(f"执行搜索任务失败: {str(e)}")
        if workflow_execution:
            workflow_execution.status = 'failed'
            db.session.commit()
            notify_clients('task_update', {
                'task_id': workflow_execution.id,
                'status': 'failed',
                'message': str(e)
            })
        return False

# 路由和视图函数
class User(UserMixin):
    pass

@login_manager.user_loader
def load_user(user_id):
    return User()

@app.route('/')
def index():
    """首页"""
    recent_tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(10).all()
    return render_template('index.html', tickets=recent_tickets)

@app.route('/search', methods=['POST'])
@limiter.limit("10 per minute")
def search():
    """搜索并创建新任务"""
    keyword = request.form.get('keyword', '')
    app.logger.info(f"收到搜索请求，关键词: {keyword}")
    
    try:
        app.logger.info("开始执行搜索任务")
        result = execute_search_task(keyword)  # 直接同步执行
        return jsonify({'success': result})
    except Exception as e:
        app.logger.error(f"搜索请求处理失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tickets', methods=['GET'])
@cache.cached(timeout=60)
def get_tickets():
    """获取票务信息API"""
    try:
        task_id = request.args.get('task_id')
        query = Ticket.query.join(Note)
        
        if task_id:
            task = WorkflowExecution.query.get(task_id)
            if task and task.created_at:
                query = query.filter(Ticket.created_at >= task.created_at)
        
        tickets = query.order_by(Ticket.created_at.desc()).limit(50).all()
        return jsonify([{
            'id': t.id,
            'event_name': t.event_name,
            'city': t.city,
            'event_date': t.event_date.strftime('%Y-%m-%d') if t.event_date else None,
            'area': t.area,
            'price': t.price,
            'quantity': t.quantity,
            'contact': t.contact,
            'notes': t.notes,
            'note_url': t.note.note_url if t.note else None,
            'created_at': t.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for t in tickets])
    except Exception as e:
        app.logger.error(f"获取票务信息失败: {str(e)}")
        return jsonify([])

@app.route('/api/monitor/start', methods=['POST'])
@login_required
def start_monitor():
    """启动监控"""
    monitor.start()
    return jsonify({"status": "success", "message": "Monitor started"})

@app.route('/api/monitor/stop', methods=['POST'])
@login_required
def stop_monitor():
    """停止监控"""
    monitor.stop()
    return jsonify({"status": "success", "message": "Monitor stopped"})

@app.route('/api/monitor/add_keyword', methods=['POST'])
def add_monitor_keyword():
    """添加监控关键词"""
    keyword = request.form.get('keyword', '')
    if not keyword:
        return jsonify({'success': False, 'error': '关键词不能为空'})
    
    try:
        monitor.add_keyword(keyword)
        return jsonify({'success': True, 'message': f'已添加关键词：{keyword}'})
    except Exception as e:
        app.logger.error(f"添加监控关键词失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/monitor/remove_keyword', methods=['POST'])
def remove_monitor_keyword():
    """移除监控关键词"""
    keyword = request.form.get('keyword', '')
    if not keyword:
        return jsonify({'success': False, 'error': '关键词不能为空'})
    
    try:
        monitor.remove_keyword(keyword)
        return jsonify({'success': True, 'message': f'已移除关键词：{keyword}'})
    except Exception as e:
        app.logger.error(f"移除监控关键词失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/stream')
def stream():
    """事件流接口"""
    def event_stream():
        try:
            while True:
                try:
                    # 每30秒发送一次心跳包
                    message = event_queue.get(timeout=30)
                    if message:
                        yield f"data: {json.dumps(message)}\n\n"
                except Empty:
                    # 发送心跳包保持连接
                    yield ": heartbeat\n\n"
                    continue
                except Exception as e:
                    app.logger.error(f"事件流处理错误: {str(e)}")
                    break
        except GeneratorExit:
            app.logger.info("客户端断开连接")
        except Exception as e:
            app.logger.error(f"事件流发生错误: {str(e)}")
    
    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # 禁用 Nginx 缓冲
        }
    )

def notify_clients(event_type, data):
    """向所有连接的客户端发送事件"""
    message = {
        'type': event_type,
        'data': data,
        'timestamp': datetime.now().isoformat()
    }
    event_queue.put(message)

@app.route('/tasks', methods=['GET'])
def get_tasks():
    """获取任务列表"""
    try:
        tasks = WorkflowExecution.query.order_by(
            WorkflowExecution.created_at.desc()
        ).limit(20).all()
        
        return jsonify([{
            'id': task.id,
            'code': task.code or 200,
            'cost': task.cost,
            'msg': task.msg or '搜索任务',
            'status': task.status or 'completed',
            'message': task.message or '',
            'is_scheduled': task.is_scheduled if hasattr(task, 'is_scheduled') else False,
            'schedule_interval': task.schedule_interval if hasattr(task, 'schedule_interval') else 60,
            'run_count': task.run_count if hasattr(task, 'run_count') else 0,
            'last_run_at': task.last_run_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(task, 'last_run_at') and task.last_run_at else None,
            'next_run_at': task.next_run_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(task, 'next_run_at') and task.next_run_at else None,
            'created_at': task.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for task in tasks])
    except Exception as e:
        app.logger.error(f"获取任务列表失败: {str(e)}")
        return jsonify([])

@app.route('/tasks/<int:task_id>/stop', methods=['POST'])
def stop_task(task_id):
    """停止任务"""
    try:
        workflow_execution = WorkflowExecution.query.get(task_id)
        if workflow_execution:
            # 移除定时任务
            monitor.remove_task_schedule(task_id)
            
            workflow_execution.status = 'stopped'
            workflow_execution.is_scheduled = False
            workflow_execution.message = "任务已停止"
            db.session.commit()
            
            notify_clients('task_update', {
                'task_id': task_id, 
                'status': 'stopped',
                'message': '任务已停止'
            })
            return jsonify({'success': True, 'message': '任务已停止'})
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/tasks/<int:task_id>/pause', methods=['POST'])
def pause_task(task_id):
    """暂停任务"""
    try:
        success = monitor.pause_task_schedule(task_id)
        if success:
            notify_clients('task_update', {
                'task_id': task_id, 
                'status': 'paused',
                'message': '任务已暂停'
            })
            return jsonify({'success': True, 'message': '任务已暂停'})
        return jsonify({'success': False, 'message': '暂停失败'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/tasks/<int:task_id>/resume', methods=['POST'])
def resume_task(task_id):
    """恢复任务"""
    try:
        success = monitor.resume_task_schedule(task_id)
        if success:
            notify_clients('task_update', {
                'task_id': task_id, 
                'status': 'running',
                'message': '任务已恢复'
            })
            return jsonify({'success': True, 'message': '任务已恢复'})
        return jsonify({'success': False, 'message': '恢复失败'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    """删除任务及相关数据"""
    try:
        # 先移除定时任务
        monitor.remove_task_schedule(task_id)
        
        workflow_execution = WorkflowExecution.query.get(task_id)
        if workflow_execution:
            # 获取任务创建时间，用于查找相关数据
            task_created_at = workflow_execution.created_at
            
            # 查找在任务创建时间之后创建的票务信息
            tickets = Ticket.query.join(Note).filter(
                Ticket.created_at >= task_created_at
            ).all()
            
            # 收集所有相关的note_ids
            note_ids = set(ticket.note_id for ticket in tickets)
            
            # 删除票务信息
            for ticket in tickets:
                db.session.delete(ticket)
            
            # 删除相关的笔记
            for note_id in note_ids:
                note = Note.query.get(note_id)
                if note:
                    db.session.delete(note)
            
            # 删除任务记录
            if workflow_execution.status == 'running':
                workflow_execution.status = 'stopped'
            db.session.delete(workflow_execution)
            
            # 提交所有更改
            db.session.commit()
            
            # 通知客户端
            notify_clients('task_update', {'task_id': task_id, 'action': 'deleted'})
            return jsonify({'success': True, 'message': '任务及相关数据已删除'})
            
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    except Exception as e:
        app.logger.error(f"删除任务失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

def update_task_status(task_id, status, message=None):
    """更新任务状态并通知客户端"""
    try:
        workflow_execution = WorkflowExecution.query.get(task_id)
        if workflow_execution:
            workflow_execution.status = status
            if message:
                workflow_execution.msg = message
            db.session.commit()
            notify_clients('task_update', {
                'task_id': task_id,
                'status': status,
                'message': message
            })
    except Exception as e:
        app.logger.error(f"更新任务状态失败: {str(e)}")

def main():
    """主函数"""
    logger.info("开始启动TicketHunter服务...")
    
    # 初始化数据库
    with app.app_context():
        db.create_all()
    
    # 启动监控服务
    monitor.start()
    logger.info("定时任务监控服务已启动")
    
    # 启动服务
    try:
        app.run(host='0.0.0.0', port=8888, debug=app.config['DEBUG'])
    except Exception as e:
        logger.error(f"Flask应用启动失败: {str(e)}")
        sys.exit(1)
    finally:
        # 停止监控服务
        monitor.stop()
        logger.info("监控服务已停止")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("正在停止服务...")
        sys.exit(0) 