"""
手动添加视频监控
"""
from flask import Blueprint, request, jsonify
from models import db
from models.monitor import MonitorTask, MonitorContent
from datetime import datetime, timezone, timedelta

# 东八区时区
TZ_SHANGHAI = timezone(timedelta(hours=8))

def get_now_time():
    """获取当前东八区时间"""
    return datetime.now(TZ_SHANGHAI)
import subprocess
import os
import re
import requests

manual_bp = Blueprint('manual', __name__)

BILI_TEMP_DIR = '/home/clawdbot/.openclaw/workspace/bili_monitor'
COOKIE_FILE = '/home/clawdbot/.openclaw/workspace/bilibili_cookies.txt'
os.makedirs(BILI_TEMP_DIR, exist_ok=True)

# 读取Cookie
def get_bili_cookie():
    cookie_path = '/home/clawdbot/.openclaw/workspace/bilibili_cookie.txt'
    if not os.path.exists(cookie_path):
        return ""
    with open(cookie_path, 'r') as f:
        sessdata = f.read().strip()
    return sessdata


def download_bili_subtitle_with_cookie(url):
    """使用bilibili_api下载字幕（需要cookie）"""
    import asyncio
    from bilibili_api import Credential, video
    
    bvid_match = re.search(r'BV[\w]+', url)
    if not bvid_match:
        return None, "无法提取BV号"
    
    bvid = bvid_match.group()
    
    # 读取cookie
    sessdata = get_bili_cookie()
    if not sessdata:
        return None, "未配置B站Cookie"
    
    async def _get_subtitle():
        try:
            cred = Credential(sessdata=sessdata, bili_jct="1234567890abcdef")
            v = video.Video(bvid=bvid, credential=cred)
            info = await v.get_info()
            subtitles = await v.get_subtitle(cid=info['cid'])
            
            # 找中文字幕
            for sub in subtitles.get('subtitles', []):
                if sub.get('lan') == 'ai-zh':
                    subtitle_url = 'https:' + sub['subtitle_url']
                    resp = requests.get(subtitle_url)
                    return resp.content, None
            return None, "未找到中文字幕"
        except Exception as e:
            return None, str(e)
    
    return asyncio.run(_get_subtitle())


def download_bili_subtitle_api(url):
    """使用B站API下载字幕"""
    import time
    
    bvid_match = re.search(r'BV[\w]+', url)
    if not bvid_match:
        return None, "无法提取BV号"
    
    bvid = bvid_match.group()
    
    try:
        # 1. 获取cid
        pagelist_url = f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}"
        resp = requests.get(pagelist_url, timeout=10)
        data = resp.json()
        if data.get('code') != 0:
            return None, f"获取视频信息失败: {data.get('message')}"
        
        cid = data['data'][0]['cid']
        
        # 2. 获取字幕列表
        subtitle_url = f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}"
        
        # 添加更多headers模拟浏览器
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com",
        }
        cookie = get_bili_cookie()
        if cookie:
            headers["Cookie"] = cookie
        
        resp = requests.get(subtitle_url, headers=headers, timeout=10)
        
        # 检查是否返回412
        if resp.status_code == 412:
            return None, "B站风控拦截，请手动复制字幕内容"
        
        data = resp.json()
        
        subtitle_list = data.get('data', {}).get('subtitle', {}).get('subtitles', [])
        if not subtitle_list:
            return None, "未找到字幕"
        
        # 3. 获取字幕数据
        subtitle_data = subtitle_list[0]
        subtitle_file_url = subtitle_data.get('subtitle_url')
        if not subtitle_file_url:
            return None, "字幕URL无效"
        
        # 处理相对URL
        if subtitle_file_url.startswith('//'):
            subtitle_file_url = 'https:' + subtitle_file_url
        
        # 替换auth_key为当前时间
        if '?' in subtitle_file_url:
            base_url, query = subtitle_file_url.split('?', 1)
            params = query.split('&')
            new_params = []
            for p in params:
                if p.startswith('auth_key='):
                    ts = str(int(time.time()) + 3600)
                    new_params.append(f"auth_key={ts}-" + p.split('-', 1)[1] if '-' in p else f"auth_key={ts}")
                else:
                    new_params.append(p)
            subtitle_file_url = base_url + '?' + '&'.join(new_params)
        
        resp = requests.get(subtitle_file_url, timeout=10)
        subtitle_json = resp.json()
        
        # 4. 解析字幕
        subtitles = subtitle_json.get('body', [])
        if not subtitles:
            return None, "字幕内容为空"
        
        # 转换为文本
        text_content = []
        for sub in subtitles:
            content = sub.get('content', '')
            text_content.append(content)
        
        return '\n'.join(text_content), None
        
    except Exception as e:
        return None, str(e)


def download_bili_subtitle(url):
    """下载B站视频字幕（优先用cookie，备选Lux）"""
    bvid_match = re.search(r'BV[\w]+', url)
    if not bvid_match:
        return None, "无法提取BV号"
    
    bvid = bvid_match.group()
    
    # 1. 优先用cookie获取字幕
    subtitle_content, error = download_bili_subtitle_with_cookie(url)
    if subtitle_content:
        # 解析JSON字幕
        import json
        try:
            data = json.loads(subtitle_content)
            body = data.get('body', [])
            texts = []
            for item in body:
                content = item.get('content', '')
                if content:
                    texts.append(content)
            return '\n'.join(texts), None
        except Exception as e:
            return None, f"解析字幕失败: {str(e)}"
    
    # 2. 备选：用Lux获取
    # （保留原有逻辑...）
    video_title = ""
    
    # 用Lux只下载字幕
    try:
        # 先获取视频标题
        cmd_info = [
            '/tmp/lux',
            '-i', '-j',
            url
        ]
        result = subprocess.run(cmd_info, capture_output=True, text=True, timeout=60, cwd=BILI_TEMP_DIR)
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                if data and len(data) > 0:
                    video_title = data[0].get('title', '')[:50]
            except:
                pass
        
        # 下载视频+字幕（用最小画质）
        cmd = [
            '/tmp/lux',
            '-f', '16-12',  # 最小画质
            '-C',              # 下载字幕
            '-o', BILI_TEMP_DIR,
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=BILI_TEMP_DIR)
        
        # 查找字幕文件
        subtitle_text = None
        
        for f in os.listdir(BILI_TEMP_DIR):
            # 优先找字幕文件
            if f.endswith('.srt'):
                filepath = os.path.join(BILI_TEMP_DIR, f)
                with open(filepath, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                # 提取字幕文本
                texts = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', content)
                texts = texts.replace('\n\n', '\n').strip()
                if len(texts) > 50:
                    subtitle_text = texts
                    break
        
        # 如果没有字幕，用弹幕作为备选
        if not subtitle_text:
            for f in os.listdir(BILI_TEMP_DIR):
                if f.endswith('.xml'):
                    filepath = os.path.join(BILI_TEMP_DIR, f)
                    with open(filepath, 'r', encoding='utf-8') as fp:
                        content = fp.read()
                    # 提取弹幕
                    danmaku = re.findall(r'<d[^>]*>([^<]+)</d>', content)
                    if danmaku:
                        # 取最新的500条弹幕
                        subtitle_text = "【弹幕内容】\n" + '\n'.join(danmaku[-500:])
                        break
        
        # 清理临时文件
        for f in os.listdir(BILI_TEMP_DIR):
            if f.endswith(('.mp4', '.m4a', '.xml', '.srt')):
                try:
                    os.remove(os.path.join(BILI_TEMP_DIR, f))
                except:
                    pass
        
        if subtitle_text:
            return subtitle_text, None
        
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
    
    # 规范化URL（去除末尾斜杠）
    url = url.rstrip('/')
    
    # 下载字幕
    subtitle, error = download_bili_subtitle(url)
    
    content = MonitorContent(
        task_id=task_id,
        content_type='video',
        title=title or url,
        content=subtitle or '',
        url=url,
        publish_time=get_now_time(),
        fetch_time=get_now_time(),
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
            publish_time=get_now_time(),
            fetch_time=get_now_time(),
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


@manual_bp.route('/bili-login', methods=['POST'])
def bili_qr_login():
    """B站二维码登录"""
    import asyncio
    from bilibili_api import login_v2, Credential
    
    async def _login():
        try:
            # 创建二维码登录对象
            qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB)
            
            # 生成二维码并保存
            await qr.generate_qrcode()
            picture = qr.get_qrcode_picture()
            picture.to_file('/home/clawdbot/.openclaw/workspace/bilibili_login_qr.png')
            
            # 等待登录
            while not qr.has_done():
                state = await qr.check_state()
                if state == login_v2.QrCodeLoginEvents.DONE:
                    break
                await asyncio.sleep(2)
            
            # 登录成功，保存cookie
            cred = qr.get_credential()
            cookies = cred.get_cookies()
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            
            with open('/home/clawdbot/.openclaw/workspace/bilibili_cookie.txt', 'w') as f:
                f.write(cookie_str)
            
            return {"success": True, "message": "登录成功"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    result = asyncio.run(_login())
    return jsonify(result)


@manual_bp.route('/bili-status', methods=['GET'])
def bili_login_status():
    """检查B站登录状态"""
    cookie_path = '/home/clawdbot/.openclaw/workspace/bilibili_cookie.txt'
    if os.path.exists(cookie_path):
        with open(cookie_path, 'r') as f:
            sessdata = f.read().strip()
        if sessdata:
            return jsonify({"success": True, "logged_in": True})
    return jsonify({"success": True, "logged_in": False})
