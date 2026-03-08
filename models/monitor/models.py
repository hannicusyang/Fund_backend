# -*- coding: utf-8 -*-
"""
资讯监控数据库模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MonitorAccount(Base):
    """平台账号表"""
    __tablename__ = 'monitor_accounts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, comment='平台名称: bilibili, youtube')
    account_name = Column(String(100), nullable=False, comment='账号名称')
    cookie = Column(Text, comment='登录 Cookie')
    config = Column(JSON, comment='额外配置')
    status = Column(Integer, default=1, comment='状态: 1=启用 0=禁用')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'platform': self.platform,
            'account_name': self.account_name,
            'status': self.status,
            'config': self.config,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }


class MonitorTask(Base):
    """监控任务表"""
    __tablename__ = 'monitor_tasks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False, comment='任务名称')
    platform = Column(String(50), nullable=False, comment='平台: bilibili')
    rss_route = Column(String(200), nullable=False, comment='RSS路由')
    route_params = Column(JSON, comment='路由参数 {"uid": "xxx"}')
    max_results = Column(Integer, default=20, comment='最大获取数量')
    cron_expression = Column(String(50), comment='Cron表达式')
    ai_prompt = Column(Text, comment='AI分析提示词')
    ai_model = Column(String(50), comment='AI模型名称')
    account_id = Column(Integer, ForeignKey('monitor_accounts.id'), comment='绑定的账号')
    enabled = Column(Boolean, default=True, comment='是否启用')
    last_run_at = Column(DateTime, comment='上次运行时间')
    created_at = Column(DateTime, default=datetime.now)
    
    account = relationship('MonitorAccount', backref='tasks')
    logs = relationship('MonitorLog', backref='task', cascade='all, delete-orphan')
    results = relationship('MonitorResult', backref='task', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_name': self.task_name,
            'platform': self.platform,
            'rss_route': self.rss_route,
            'route_params': self.route_params,
            'max_results': self.max_results or 20,
            'cron_expression': self.cron_expression,
            'ai_prompt': self.ai_prompt,
            'ai_model': self.ai_model,
            'account_id': self.account_id,
            'enabled': self.enabled,
            'last_run_at': self.last_run_at.strftime('%Y-%m-%d %H:%M:%S') if self.last_run_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class MonitorLog(Base):
    """任务日志表"""
    __tablename__ = 'monitor_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('monitor_tasks.id'), comment='任务ID')
    level = Column(String(20), default='INFO', comment='日志级别: DEBUG, INFO, WARNING, ERROR')
    message = Column(Text, nullable=False, comment='日志内容')
    created_at = Column(DateTime, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'level': self.level,
            'message': self.message,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class MonitorResult(Base):
    """任务结果表"""
    __tablename__ = 'monitor_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('monitor_tasks.id'), comment='任务ID')
    video_title = Column(String(500), comment='视频标题')
    video_url = Column(String(500), comment='视频链接')
    video_author = Column(String(100), comment='作者')
    video_desc = Column(Text, comment='视频描述')
    video_publish_time = Column(DateTime, comment='发布时间')
    subtitle_content = Column(Text, comment='字幕内容')
    ai_summary = Column(Text, comment='AI总结')
    ai_reasoning = Column(Text, comment='AI分析理由')
    created_at = Column(DateTime, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'video_title': self.video_title,
            'video_url': self.video_url,
            'video_author': self.video_author,
            'video_desc': self.video_desc,
            'video_publish_time': self.video_publish_time.strftime('%Y-%m-%d %H:%M:%S') if self.video_publish_time else None,
            'subtitle_content': self.subtitle_content,
            'ai_summary': self.ai_summary,
            'ai_reasoning': self.ai_reasoning,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class MonitorContent(Base):
    """监控内容表 (兼容旧版)"""
    __tablename__ = 'monitor_contents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('monitor_tasks.id'), comment='任务ID')
    platform = Column(String(20), comment='平台')  # 新增：平台
    url = Column(String(500), comment='内容链接')
    title = Column(String(500), comment='标题')
    author = Column(String(100), comment='作者')
    description = Column(Text, comment='描述')
    publish_time = Column(DateTime, comment='发布时间')
    subtitle_content = Column(Text, comment='字幕原文')
    ai_summary = Column(Text, comment='AI总结')
    created_at = Column(DateTime, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'platform': self.platform,
            'url': self.url,
            'title': self.title,
            'author': self.author,
            'description': self.description,
            'subtitle_content': self.subtitle_content,
            'ai_summary': self.ai_summary,
            'publish_time': self.publish_time.strftime('%Y-%m-%d %H:%M:%S') if self.publish_time else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class MonitorSettings(Base):
    """系统设置表"""
    __tablename__ = 'monitor_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(50), unique=True, nullable=False, comment='设置键')
    setting_value = Column(Text, comment='设置值')
    description = Column(String(200), comment='说明')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'setting_key': self.setting_key,
            'setting_value': self.setting_value,
            'description': self.description,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }


# 默认设置
DEFAULT_SETTINGS = {
    'ai_model': 'gpt-4o',
    'ai_base_url': 'https://api.openai.com/v1',
    'ai_api_key': '',
    'notify_enabled': 'false',
    'notify_type': 'feishu',
    'notify_webhook': ''
}
