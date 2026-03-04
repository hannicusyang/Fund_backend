"""
手动添加视频监控
"""
from flask import Blueprint, request, jsonify
from models import db
from models.monitor import MonitorTask, MonitorContent
from datetime import datetime
import subprocess
import os
import re

manual_bp = Blueprint('manual', __name__)

BILI_TEMP_DIR = '/home/clawdbot/.openclaw/workspace/bili_monitor'
COOKIE_FILE = '/home/clawdbot/.openclaw/workspace/bilibili_cookies.txt'
os.makedirs(BILI_TEMP_DIR, exist_ok=True)


def download_bili_subtitle(url):
    """下载B站视频字幕"""
    # 提取bvid
    bvid_match = re.search(r'BV[\w]+', url)
    if not bvid_match:
        return None, "无法提取BV号"
    
    bvid = bvid_match.group()
    
    try:
        cmd = [
            'yt-dlp',
            '--write-subs',
            '--sub-lang', 'ai-zh',
            '--skip-download',
            '--output', f'{BILI_TEMP_DIR}/{bvid}.%(ext)s'
        ]
        
        if os.path.exists(COOKIE_FILE):
            cmd.extend(['--cookies', COOKIE_FILE])
        
        cmd.append(url)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # 查找字幕文件
        for f in os.listdir(BILI_TEMP_DIR):
            if bvid in f and f.endswith('.srt'):
                with open(os.path.join(BILI_TEMP_DIR, f), 'r', encoding='utf-8') as fp:
                    content = fp.read()
                os.remove(os.path.join(BILI_TEMP_DIR, f))
                return content, None
        
        return None, "未找到字幕"
        
    except Exception as e:
        return None, str(e)


@manual_bp.route('/add-video', methods=['POST'])
def add_video():
    """手动添加视频监控"""
    data = request.json
    url = data.get('url', '')
    task_id = data.get('task_id')
    title = data.get('title', '')
    
    if not url or not task_id:
        return jsonify({"success": False, "message": "缺少参数"}), 400
    
    # 检查是否已存在
    existing = MonitorContent.query.filter_by(task_id=task_id, url=url).first()
    if existing:
        return jsonify({"success": False, "message": "视频已存在"}), 400
    
    # 下载字幕
    subtitle, error = download_bili_subtitle(url)
    
    content = MonitorContent(
        task_id=task_id,
        content_type='video',
        title=title or url,
        content=subtitle or '',
        url=url,
        publish_time=datetime.utcnow(),
        fetch_time=datetime.utcnow(),
        status='pending' if subtitle else ('error' if error else 'pending')
    )
    db.session.add(content)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "data": {
            "id": content.id,
            "title": content.title,
            "has_subtitle": bool(subtitle),
            "error": error
        }
    })


@manual_bp.route('/batch-add', methods=['POST'])
def batch_add_videos():
    """批量添加视频URL"""
    data = request.json
    urls = data.get('urls', [])  # 数组
    task_id = data.get('task_id')
    
    if not urls or not task_id:
        return jsonify({"success": False, "message": "缺少参数"}), 400
    
    results = []
    for url in urls:
        # 检查是否已存在
        existing = MonitorContent.query.filter_by(task_id=task_id, url=url).first()
        if existing:
            results.append({"url": url, "status": "exists"})
            continue
        
        # 下载字幕
        subtitle, error = download_bili_subtitle(url)
        
        content = MonitorContent(
            task_id=task_id,
            content_type='video',
            title=url,
            content=subtitle or '',
            url=url,
            publish_time=datetime.utcnow(),
            fetch_time=datetime.utcnow(),
            status='pending' if subtitle else ('error' if error else 'pending')
        )
        db.session.add(content)
        results.append({
            "url": url,
            "status": "ok" if subtitle else "error",
            "error": error
        })
    
    db.session.commit()
    
    return jsonify({
        "success": True,
        "data": {
            "total": len(urls),
            "results": results
        }
    })
