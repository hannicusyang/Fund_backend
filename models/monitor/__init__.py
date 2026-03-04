# 监控账号模型
from models import db
from datetime import datetime
import json


class MonitorAccount(db.Model):
    """监控账号表"""
    __tablename__ = 'monitor_account'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    platform = db.Column(db.String(20), nullable=False, comment='平台: bilibili/douyin/wechat')
    account_name = db.Column(db.String(100), comment='账号/UP主名称')
    account_id = db.Column(db.String(100), comment='平台账号ID')
    cookie = db.Column(db.Text, comment='加密后的Cookie')
    status = db.Column(db.String(20), default='active', comment='状态: active/inactive')
    remark = db.Column(db.String(255), comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    tasks = db.relationship('MonitorTask', backref='account', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'platform': self.platform,
            'account_name': self.account_name,
            'account_id': self.account_id,
            'status': self.status,
            'remark': self.remark,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class MonitorTask(db.Model):
    """监控任务表"""
    __tablename__ = 'monitor_task'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.Integer, db.ForeignKey('monitor_account.id'), comment='账号ID')
    task_name = db.Column(db.String(100), nullable=False, comment='任务名称')
    platform = db.Column(db.String(20), nullable=False, comment='平台')
    target_type = db.Column(db.String(20), comment='up主/关键词')
    target_value = db.Column(db.String(255), comment='目标值(UP主ID或关键词)')
    schedule = db.Column(db.String(50), comment='Cron表达式')
    is_enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    contents = db.relationship('MonitorContent', backref='task', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'task_name': self.task_name,
            'platform': self.platform,
            'target_type': self.target_type,
            'target_value': self.target_value,
            'schedule': self.schedule,
            'is_enabled': self.is_enabled,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class MonitorContent(db.Model):
    """监控内容记录表"""
    __tablename__ = 'monitor_content'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('monitor_task.id'), comment='任务ID')
    content_type = db.Column(db.String(20), comment='video/article')
    title = db.Column(db.String(255), comment='标题')
    content = db.Column(db.Text, comment='内容/字幕')
    summary = db.Column(db.Text, comment='AI总结')
    url = db.Column(db.String(500), comment='原文链接')
    publish_time = db.Column(db.DateTime, comment='发布时间')
    fetch_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_new = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default='pending', comment='pending/summarized/error')
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'content_type': self.content_type,
            'title': self.title,
            'summary': self.summary,
            'url': self.url,
            'publish_time': self.publish_time.isoformat() if self.publish_time else None,
            'fetch_time': self.fetch_time.isoformat() if self.fetch_time else None,
            'is_new': self.is_new,
            'status': self.status
        }
