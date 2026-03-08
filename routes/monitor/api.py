# -*- coding: utf-8 -*-
"""
资讯监控 API 路由
"""
from flask import Blueprint, request, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

from models.monitor.models import (
    MonitorAccount, MonitorTask, MonitorLog, MonitorResult, MonitorContent, MonitorSettings, DEFAULT_SETTINGS
)

monitor_bp = Blueprint('monitor', __name__, url_prefix='/api/monitor')

# 数据库连接
DATABASE_URL = 'sqlite:///./fund_monitor.db'
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)


def get_session():
    return Session()


def init_db():
    """初始化数据库"""
    from models.monitor.models import Base
    Base.metadata.create_all(engine)


# 初始化数据库
init_db()


# ==================== 平台账号管理 ====================

@monitor_bp.route('/accounts', methods=['GET'])
def get_accounts():
    """获取账号列表"""
    session = get_session()
    try:
        platform = request.args.get('platform')
        query = session.query(MonitorAccount)
        if platform:
            query = query.filter(MonitorAccount.platform == platform)
        accounts = query.order_by(MonitorAccount.created_at.desc()).all()
        return jsonify({
            'code': 0,
            'data': [a.to_dict() for a in accounts]
        })
    finally:
        session.close()


@monitor_bp.route('/accounts', methods=['POST'])
def create_account():
    """创建账号"""
    session = get_session()
    try:
        data = request.json
        account = MonitorAccount(
            platform=data.get('platform'),
            account_name=data.get('account_name'),
            cookie=data.get('cookie', ''),
            config=data.get('config', {}),
            status=data.get('status', 1)
        )
        session.add(account)
        session.commit()
        return jsonify({'code': 0, 'data': account.to_dict()})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


@monitor_bp.route('/accounts/<int:account_id>', methods=['PUT'])
def update_account(account_id):
    """更新账号"""
    session = get_session()
    try:
        account = session.query(MonitorAccount).get(account_id)
        if not account:
            return jsonify({'code': 1, 'message': '账号不存在'}), 404
        
        data = request.json
        if 'account_name' in data:
            account.account_name = data['account_name']
        if 'cookie' in data:
            account.cookie = data['cookie']
        if 'config' in data:
            account.config = data['config']
        if 'status' in data:
            account.status = data['status']
        if 'platform' in data:
            account.platform = data['platform']
        
        account.updated_at = datetime.now()
        session.commit()
        return jsonify({'code': 0, 'data': account.to_dict()})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


@monitor_bp.route('/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """删除账号"""
    session = get_session()
    try:
        account = session.query(MonitorAccount).get(account_id)
        if not account:
            return jsonify({'code': 1, 'message': '账号不存在'}), 404
        session.delete(account)
        session.commit()
        return jsonify({'code': 0})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


# ==================== 监控任务管理 ====================

@monitor_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """获取任务列表"""
    session = get_session()
    try:
        platform = request.args.get('platform')
        enabled = request.args.get('enabled')
        query = session.query(MonitorTask)
        if platform:
            query = query.filter(MonitorTask.platform == platform)
        if enabled is not None:
            query = query.filter(MonitorTask.enabled == (enabled == 'true'))
        tasks = query.order_by(MonitorTask.created_at.desc()).all()
        return jsonify({
            'code': 0,
            'data': [t.to_dict() for t in tasks]
        })
    finally:
        session.close()


@monitor_bp.route('/tasks', methods=['POST'])
def create_task():
    """创建任务"""
    session = get_session()
    try:
        data = request.json
        task = MonitorTask(
            task_name=data.get('task_name'),
            platform=data.get('platform'),
            rss_route=data.get('rss_route'),
            route_params=data.get('route_params', {}),
            max_results=data.get('max_results', 20),
            cron_expression=data.get('cron_expression'),
            ai_prompt=data.get('ai_prompt', '请总结这个视频的主要内容'),
            ai_model=data.get('ai_model'),
            account_id=data.get('account_id'),
            enabled=data.get('enabled', True)
        )
        session.add(task)
        session.commit()
        return jsonify({'code': 0, 'data': task.to_dict()})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


@monitor_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """更新任务"""
    session = get_session()
    try:
        task = session.query(MonitorTask).get(task_id)
        if not task:
            return jsonify({'code': 1, 'message': '任务不存在'}), 404
        
        data = request.json
        for key in ['task_name', 'platform', 'rss_route', 'route_params', 'max_results',
                   'cron_expression', 'ai_prompt', 'ai_model', 'account_id', 'enabled']:
            if key in data:
                setattr(task, key, data[key])
        
        session.commit()
        return jsonify({'code': 0, 'data': task.to_dict()})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


@monitor_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    session = get_session()
    try:
        task = session.query(MonitorTask).get(task_id)
        if not task:
            return jsonify({'code': 1, 'message': '任务不存在'}), 404
        session.delete(task)
        session.commit()
        return jsonify({'code': 0})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


@monitor_bp.route('/tasks/<int:task_id>/run', methods=['POST'])
def run_task(task_id):
    """手动运行任务"""
    session = get_session()
    try:
        task = session.query(MonitorTask).get(task_id)
        if not task:
            return jsonify({'code': 1, 'message': '任务不存在'}), 404
        
        # 添加日志
        log = MonitorLog(
            task_id=task_id,
            level='INFO',
            message=f'任务手动触发执行'
        )
        session.add(log)
        session.commit()
        
        # 实际执行任务（异步）
        import threading
        def execute_task():
            from services.monitor.scheduler import run_monitor_task
            run_monitor_task(task_id)
        
        thread = threading.Thread(target=execute_task)
        thread.start()
        
        return jsonify({
            'code': 0, 
            'message': '任务已触发执行',
            'data': {'task_id': task_id}
        })
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


# ==================== 任务日志 ====================

@monitor_bp.route('/logs', methods=['GET'])
def get_logs():
    """获取日志列表"""
    session = get_session()
    try:
        task_id = request.args.get('task_id', type=int)
        level = request.args.get('level')
        limit = request.args.get('limit', 100, type=int)
        
        query = session.query(MonitorLog)
        if task_id:
            query = query.filter(MonitorLog.task_id == task_id)
        if level:
            query = query.filter(MonitorLog.level == level)
        
        logs = query.order_by(MonitorLog.created_at.asc()).limit(limit).all()
        return jsonify({
            'code': 0,
            'data': [l.to_dict() for l in logs]
        })
    finally:
        session.close()


@monitor_bp.route('/logs/clear', methods=['POST'])
def clear_logs():
    """清空日志"""
    session = get_session()
    try:
        task_id = request.args.get('task_id', type=int)
        
        if task_id:
            session.query(MonitorLog).filter(MonitorLog.task_id == task_id).delete()
        else:
            session.query(MonitorLog).delete()
        
        session.commit()
        return jsonify({'code': 0, 'message': '日志已清空'})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


@monitor_bp.route('/logs/stream', methods=['GET'])
def stream_logs():
    """日志流（模拟实时日志）"""
    session = get_session()
    try:
        task_id = request.args.get('task_id', type=int)
        query = session.query(MonitorLog)
        if task_id:
            query = query.filter(MonitorLog.task_id == task_id)
        logs = query.order_by(MonitorLog.created_at.asc()).limit(50).all()
        return jsonify({
            'code': 0,
            'data': [l.to_dict() for l in logs]
        })
    finally:
        session.close()


# ==================== 结果查看 ====================

@monitor_bp.route('/results', methods=['GET'])
def get_results():
    """获取结果列表"""
    session = get_session()
    try:
        task_id = request.args.get('task_id', type=int)
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        query = session.query(MonitorContent)
        if task_id:
            query = query.filter(MonitorContent.task_id == task_id)
        
        total = query.count()
        results = query.order_by(MonitorContent.created_at.desc()).offset(offset).limit(limit).all()
        
        return jsonify({
            'code': 0,
            'data': [r.to_dict() for r in results],
            'total': total
        })
    finally:
        session.close()


@monitor_bp.route('/results/<int:result_id>', methods=['GET'])
def get_result(result_id):
    """获取结果详情"""
    session = get_session()
    try:
        result = session.query(MonitorResult).get(result_id)
        if not result:
            return jsonify({'code': 1, 'message': '结果不存在'}), 404
        return jsonify({'code': 0, 'data': result.to_dict()})
    finally:
        session.close()


@monitor_bp.route('/results/<int:result_id>', methods=['DELETE'])
def delete_result(result_id):
    """删除结果"""
    session = get_session()
    try:
        result = session.query(MonitorContent).get(result_id)
        if not result:
            return jsonify({'code': 1, 'message': '结果不存在'}), 404
        session.delete(result)
        session.commit()
        return jsonify({'code': 0})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


@monitor_bp.route('/results/batch', methods=['DELETE'])
def batch_delete_results():
    """批量删除结果"""
    session = get_session()
    try:
        data = request.json
        result_ids = data.get('result_ids', [])
        
        if not result_ids:
            return jsonify({'code': 1, 'message': '请选择要删除的内容'}), 400
        
        deleted_count = 0
        for result_id in result_ids:
            result = session.query(MonitorContent).get(result_id)
            if result:
                session.delete(result)
                deleted_count += 1
        
        session.commit()
        return jsonify({'code': 0, 'message': f'已删除 {deleted_count} 条'})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


# ==================== 系统设置 ====================

@monitor_bp.route('/settings', methods=['GET'])
def get_settings():
    """获取设置列表"""
    session = get_session()
    try:
        settings = session.query(MonitorSettings).all()
        # 如果没有设置，创建默认设置
        if not settings:
            for key, value in DEFAULT_SETTINGS.items():
                setting = MonitorSettings(
                    setting_key=key,
                    setting_value=value,
                    description=f'{key} 配置'
                )
                session.add(setting)
            session.commit()
            settings = session.query(MonitorSettings).all()
        
        return jsonify({
            'code': 0,
            'data': {s.setting_key: s.setting_value for s in settings}
        })
    finally:
        session.close()


@monitor_bp.route('/settings', methods=['PUT'])
def update_settings():
    """更新设置"""
    session = get_session()
    try:
        data = request.json
        for key, value in data.items():
            setting = session.query(MonitorSettings).filter(MonitorSettings.setting_key == key).first()
            if setting:
                setting.setting_value = value
            else:
                setting = MonitorSettings(setting_key=key, setting_value=value)
                session.add(setting)
        session.commit()
        return jsonify({'code': 0})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


@monitor_bp.route('/settings/<key>', methods=['GET'])
def get_setting(key):
    """获取单个设置"""
    session = get_session()
    try:
        setting = session.query(MonitorSettings).filter(MonitorSettings.setting_key == key).first()
        if not setting:
            default_value = DEFAULT_SETTINGS.get(key, '')
            return jsonify({'code': 0, 'data': {'key': key, 'value': default_value}})
        return jsonify({'code': 0, 'data': {'key': key, 'value': setting.setting_value}})
    finally:
        session.close()


# ==================== AI 总结 ====================

@monitor_bp.route('/results/ai-summary', methods=['POST'])
def ai_summary():
    """AI总结内容"""
    session = get_session()
    try:
        data = request.json
        result_ids = data.get('result_ids', [])
        
        if not result_ids:
            return jsonify({'code': 1, 'message': '请选择要总结的内容'}), 400
        
        # 获取系统设置
        settings = {}
        all_settings = session.query(MonitorSettings).all()
        for s in all_settings:
            settings[s.setting_key] = s.setting_value
        
        ai_model = settings.get('ai_model', 'gpt-4o')
        ai_api_key = settings.get('ai_api_key', '')
        ai_base_url = settings.get('ai_base_url', 'https://api.openai.com/v1')
        
        if not ai_api_key:
            return jsonify({'code': 1, 'message': '请先配置AI API Key'}), 400
        
        # 调用AI
        results = []
        for result_id in result_ids:
            content = session.query(MonitorContent).get(result_id)
            if not content:
                continue
            
            # 获取任务关联的账号Cookie
            account_cookie = None
            task = session.query(MonitorTask).get(content.task_id)
            print(f"DEBUG: content.task_id={content.task_id}, task.account_id={task.account_id if task else 'None'}")
            if task and task.account_id:
                account = session.query(MonitorAccount).get(task.account_id)
                print(f"DEBUG: account={account}, cookie={'有' if account and account.cookie else '无'}")
                if account and account.cookie:
                    account_cookie = account.cookie
            
            # 尝试下载字幕
            subtitle_text = download_subtitle(content.url, account_cookie)
            
            # 保存字幕原文
            if subtitle_text:
                content.subtitle_content = subtitle_text[:5000]
                # 有字幕才进行AI总结
                # 获取自定义提示词
                custom_prompt = settings.get('ai_prompt', '')
                if custom_prompt and '{content}' in custom_prompt:
                    # 使用自定义提示词，替换占位符
                    prompt = custom_prompt.replace('{content}', subtitle_text[:3000])
                else:
                    # 使用默认提示词
                    prompt = f"请用100字左右总结以下视频字幕的核心内容要点：\n\n字幕内容：\n{subtitle_text[:3000]}"
                try:
                    summary = call_ai_api(ai_base_url, ai_api_key, ai_model, prompt)
                    content.ai_summary = summary
                    results.append({'id': result_id, 'summary': summary, 'has_subtitle': True})
                except Exception as e:
                    results.append({'id': result_id, 'error': str(e)})
            else:
                # 没有字幕，不进行总结
                results.append({'id': result_id, 'error': '无法获取视频字幕，请检查账号Cookie是否有效'})
                continue
        
        session.commit()
        return jsonify({'code': 0, 'data': results})
    except Exception as e:
        session.rollback()
        return jsonify({'code': 1, 'message': str(e)}), 400
    finally:
        session.close()


def download_subtitle(url, cookie=None):
    """通过yt-dlp获取B站视频字幕"""
    import subprocess
    import re
    import os
    import tempfile
    import urllib.parse
    
    print(f"[DEBUG] download_subtitle called with url={url}, cookie={'有' if cookie else '无'}")
    
    # 提取BVID
    bvid_match = re.search(r'/(BV[\w]+)', url)
    if not bvid_match:
        bvid_match = re.search(r'/av(\d+)', url)
        if bvid_match:
            aid = bvid_match.group(1)
            print(f"[DEBUG] 提取到AID: {aid}")
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.bilibili.com/'
            }
            try:
                resp = requests.get(f'https://api.bilibili.com/x/web-interface/view?aid={aid}', timeout=10, headers=headers)
                data = resp.json()
                if data.get('code') == 0:
                    bvid = data['data']['bvid']
                    print(f"[DEBUG] 转换为BVID: {bvid}")
                else:
                    print(f"[DEBUG] API返回错误: {data}")
                    return None
            except Exception as e:
                print(f"[DEBUG] API请求失败: {e}")
                return None
        else:
            print("[DEBUG] 无法提取BVID或AID")
            return None
    else:
        bvid = bvid_match.group(1)
        print(f"[DEBUG] 直接提取BVID: {bvid}")
    
    # 创建临时cookie文件（用于yt-dlp）
    cookie_file = None
    if cookie:
        # 不需要解码，直接使用（yt-dlp需要URL编码的格式）
        temp_dir = tempfile.mkdtemp()
        cookie_path = os.path.join(temp_dir, 'cookies.txt')
        with open(cookie_path, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            # 注意：保持cookie的URL编码格式
            f.write(".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\t" + cookie + "\n")
        cookie_file = cookie_path
    
    # 创建临时输出文件
    output_file = tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8')
    output_path = output_file.name
    output_file.close()
    
    try:
        # 构建yt-dlp命令
        cmd = [
            '/home/clawdbot/.openclaw/workspace/Fund_backend/venv/bin/yt-dlp',
            '--write-subs',
            '--write-auto-subs',
            '--sub-lang', 'zh-CN,ai-zh',
            '--skip-download',
            '--output', output_path,
        ]
        
        # 添加cookie参数
        if cookie_file:
            cmd.extend(['--cookies', cookie_file])
        
        # 添加extractor参数避免412错误 - 使用player_web而非default
        cmd.extend(['--extractor-args', 'bilibili:player_web=true'])
        
        cmd.append(f'https://www.bilibili.com/video/{bvid}')
        
        print(f"[DEBUG] yt-dlp命令: {' '.join(cmd)}")
        
        # 执行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print(f"[DEBUG] yt-dlp返回码: {result.returncode}")
        print(f"[DEBUG] yt-dlp stderr: {result.stderr[-200:] if result.stderr else 'None'}")
        
        # 查找生成的字幕文件
        srt_file = output_path + '.ai-zh.srt'
        if not os.path.exists(srt_file):
            # 尝试其他可能的文件名
            for ext in ['.zh-CN.srt', '.srt']:
                alt_file = output_path + ext
                if os.path.exists(alt_file):
                    srt_file = alt_file
                    break
        
        if not os.path.exists(srt_file):
            # 尝试从输出中查找
            if 'Writing video subtitles to:' in result.stderr:
                print(f"yt-dlp输出: {result.stderr}")
            return None
        
        # 读取字幕文件
        with open(srt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取纯文本
        lines = content.split('\n')
        text_lines = []
        for line in lines:
            if '-->' not in line and line.strip() and not line.strip().isdigit():
                text_lines.append(line.strip())
        
        return ' '.join(text_lines)[:5000]
        
    except subprocess.TimeoutExpired:
        print("yt-dlp超时")
        return None
    except Exception as e:
        print(f"yt-dlp错误: {e}")
        return None
    finally:
        # 清理临时文件
        try:
            if cookie_file and os.path.exists(cookie_file):
                os.unlink(cookie_file)
                # 删除父目录
                temp_dir = os.path.dirname(cookie_file)
                if temp_dir and os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            for f in [output_path + '.ai-zh.srt', output_path + '.zh-CN.srt', output_path + '.srt']:
                if os.path.exists(f):
                    os.unlink(f)
            # 删除输出文件的父目录
            out_temp_dir = os.path.dirname(output_path)
            if out_temp_dir and os.path.exists(out_temp_dir):
                os.rmdir(out_temp_dir)
        except:
            pass


def call_ai_api(base_url, api_key, model, prompt):
    """调用AI API"""
    import requests
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # 判断API类型
    if 'minimaxi' in base_url:
        # MiniMax API (Anthropic兼容)
        url = f"{base_url}/v1/messages"
        data = {
            'model': model,
            'max_tokens': 500,
            'thinking_budget': 0,  # 禁用thinking，强制返回text
            'messages': [{'role': 'user', 'content': prompt}]
        }
    else:
        # OpenAI兼容API
        url = f"{base_url}/chat/completions"
        data = {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 500
        }
    
    response = requests.post(url, headers=headers, json=data, timeout=60)
    response.raise_for_status()
    
    result = response.json()
    
    # 兼容多种返回格式
    try:
        if 'minimaxi' in base_url:
            # MiniMax返回格式 - Anthropic兼容
            for block in result.get('content', []):
                if block.get('type') == 'text':
                    return block.get('text', '')
                elif block.get('type') == 'thinking':
                    # MiniMax返回thinking类型的内容，也作为总结
                    return block.get('thinking', '')[:500]
            return str(result)
        elif 'choices' in result:
            # OpenAI格式
            return result['choices'][0]['message']['content']
        else:
            return str(result)
    except Exception as e:
        return f"解析失败: {str(e)}, 原始响应: {result}"


