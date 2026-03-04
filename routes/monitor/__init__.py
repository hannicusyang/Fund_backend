"""
监控模块API路由
"""
from flask import Blueprint, request, jsonify
from models import db
from models.monitor import MonitorAccount, MonitorTask, MonitorContent
from datetime import datetime
import json

monitor_bp = Blueprint('monitor', __name__)


# ==================== 账号管理 ====================

@monitor_bp.route('/accounts', methods=['GET'])
def get_accounts():
    """获取监控账号列表"""
    try:
        platform = request.args.get('platform')
        query = MonitorAccount.query
        if platform:
            query = query.filter_by(platform=platform)
        accounts = query.order_by(MonitorAccount.created_at.desc()).all()
        return jsonify({
            "success": True,
            "data": [a.to_dict() for a in accounts]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route('/accounts', methods=['POST'])
def create_account():
    """添加监控账号"""
    try:
        data = request.json
        account = MonitorAccount(
            platform=data['platform'],
            account_name=data.get('account_name', ''),
            account_id=data.get('account_id', ''),
            cookie=data.get('cookie', ''),
            remark=data.get('remark', '')
        )
        db.session.add(account)
        db.session.commit()
        return jsonify({"success": True, "data": account.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route('/accounts/<int:id>', methods=['PUT'])
def update_account(id):
    """更新监控账号"""
    try:
        account = MonitorAccount.query.get_or_404(id)
        data = request.json
        if 'account_name' in data:
            account.account_name = data['account_name']
        if 'account_id' in data:
            account.account_id = data['account_id']
        if 'cookie' in data:
            account.cookie = data['cookie']
        if 'status' in data:
            account.status = data['status']
        if 'remark' in data:
            account.remark = data['remark']
        account.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"success": True, "data": account.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route('/accounts/<int:id>', methods=['DELETE'])
def delete_account(id):
    """删除监控账号"""
    try:
        account = MonitorAccount.query.get_or_404(id)
        # 删除关联的任务和内容
        MonitorTask.query.filter_by(account_id=id).delete()
        db.session.delete(account)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== 任务管理 ====================

@monitor_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """获取监控任务列表"""
    try:
        account_id = request.args.get('account_id', type=int)
        query = MonitorTask.query
        if account_id:
            query = query.filter_by(account_id=account_id)
        tasks = query.order_by(MonitorTask.created_at.desc()).all()
        return jsonify({
            "success": True,
            "data": [t.to_dict() for t in tasks]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route('/tasks', methods=['POST'])
def create_task():
    """创建监控任务"""
    try:
        data = request.json
        task = MonitorTask(
            account_id=data['account_id'],
            task_name=data['task_name'],
            platform=data['platform'],
            target_type=data.get('target_type', 'up主'),
            target_value=data.get('target_value', ''),
            schedule=data.get('schedule', '0 * * * *'),
            is_enabled=data.get('is_enabled', True)
        )
        db.session.add(task)
        db.session.commit()
        return jsonify({"success": True, "data": task.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route('/tasks/<int:id>', methods=['PUT'])
def update_task(id):
    """更新监控任务"""
    try:
        task = MonitorTask.query.get_or_404(id)
        data = request.json
        if 'task_name' in data:
            task.task_name = data['task_name']
        if 'target_value' in data:
            task.target_value = data['target_value']
        if 'schedule' in data:
            task.schedule = data['schedule']
        if 'is_enabled' in data:
            task.is_enabled = data['is_enabled']
        task.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"success": True, "data": task.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route('/tasks/<int:id>', methods=['DELETE'])
def delete_task(id):
    """删除监控任务"""
    try:
        task = MonitorTask.query.get_or_404(id)
        # 删除关联内容
        MonitorContent.query.filter_by(task_id=id).delete()
        db.session.delete(task)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route('/tasks/<int:id>/run', methods=['POST'])
def run_task(id):
    """手动执行任务"""
    try:
        task = MonitorTask.query.get_or_404(id)
        task.last_run = datetime.utcnow()
        db.session.commit()
        
        # TODO: 调用监控服务执行任务
        from services.monitor.bilibili_monitor import run_bilibili_task
        result = run_bilibili_task(task.id)
        
        return jsonify({"success": True, "message": "任务执行完成", "data": result})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== 内容管理 ====================

@monitor_bp.route('/contents', methods=['GET'])
def get_contents():
    """获取监控内容列表"""
    try:
        task_id = request.args.get('task_id', type=int)
        status = request.args.get('status')
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        
        query = MonitorContent.query
        if task_id:
            query = query.filter_by(task_id=task_id)
        if status:
            query = query.filter_by(status=status)
        
        pagination = query.order_by(MonitorContent.fetch_time.desc()).paginate(
            page=page, per_page=page_size, error_out=False
        )
        
        return jsonify({
            "success": True,
            "data": {
                "items": [c.to_dict() for c in pagination.items],
                "total": pagination.total,
                "page": page,
                "page_size": page_size
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route('/contents/<int:id>/summarize', methods=['POST'])
def summarize_content(id):
    """手动总结内容"""
    try:
        content = MonitorContent.query.get_or_404(id)
        
        # TODO: 调用AI总结服务
        from services.monitor.summarizer import summarize_text
        summary = summarize_text(content.content)
        
        content.summary = summary
        content.status = 'summarized'
        db.session.commit()
        
        return jsonify({"success": True, "data": {"summary": summary}})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@monitor_bp.route('/contents/<int:id>', methods=['GET'])
def get_content_detail(id):
    """获取内容详情"""
    try:
        content = MonitorContent.query.get_or_404(id)
        return jsonify({"success": True, "data": content.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
