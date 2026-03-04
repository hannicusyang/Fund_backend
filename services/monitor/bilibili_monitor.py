"""
B站监控服务 - 使用Playwright
"""
import os
import json
import subprocess
from datetime import datetime
from models import db
from models.monitor import MonitorAccount, MonitorTask, MonitorContent
from playwright.sync_api import sync_playwright

# 临时目录
BILI_TEMP_DIR = '/home/clawdbot/.openclaw/workspace/bili_monitor'
os.makedirs(BILI_TEMP_DIR, exist_ok=True)

# Cookie文件路径
COOKIE_FILE = '/home/clawdbot/.openclaw/workspace/bilibili_cookies.txt'


def get_up_videos_playwright(mid):
    """使用Playwright获取UP主视频列表"""
    videos = []
    
    try:
        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            # 访问UP主空间
            url = f'https://space.bilibili.com/{mid}?tab=video'
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # 等待页面加载
            page.wait_for_timeout(3000)
            
            # 尝试获取视频列表 (class可能需要调整)
            # B站视频列表的class通常是 video-card 和-like
            video_items = page.query_selector_all('.video-card')
            
            for item in video_items[:10]:  # 只取最新10个
                try:
                    title_elem = item.query_selector('.title')
                    link_elem = item.query_selector('a')
                    
                    title = title_elem.inner_text() if title_elem else ''
                    href = link_elem.get_attribute('href') if link_elem else ''
                    
                    if title and href:
                        # 提取bvid
                        bvid = href.split('/')[-1] if href else ''
                        videos.append({
                            'bvid': bvid,
                            'title': title.strip(),
                            'url': f'https://bilibili.com{href}'
                        })
                except Exception as e:
                    continue
            
            # 如果上面的方法不行，尝试另一种选择器
            if not videos:
                # 尝试 .cover-up .title
                video_items = page.query_selector_all('.cover-up')
                for item in video_items[:10]:
                    try:
                        title_elem = item.query_selector('.title')
                        link_elem = item.query_selector('a')
                        
                        title = title_elem.inner_text() if title_elem else ''
                        href = link_elem.get_attribute('href') if link_elem else ''
                        
                        if title and href:
                            bvid = href.split('/')[-1] if href else ''
                            videos.append({
                                'bvid': bvid,
                                'title': title.strip(),
                                'url': f'https://bilibili.com{href}'
                            })
                    except:
                        continue
            
            browser.close()
            
    except Exception as e:
        print(f"Playwright获取视频失败: {e}")
    
    return videos


def download_subtitle(bvid, cookie_value=None):
    """下载视频字幕"""
    try:
        cmd = [
            'yt-dlp',
            '--write-subs',
            '--sub-lang', 'ai-zh',
            '--skip-download',
            '--output', f'{BILI_TEMP_DIR}/{bvid}.%(ext)s'
        ]
        
        if cookie_value and os.path.exists(COOKIE_FILE):
            cmd.extend(['--cookies', COOKIE_FILE])
        
        cmd.append(f'https://www.bilibili.com/video/{bvid}')
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        # 查找下载的字幕文件
        subtitle_file = None
        for f in os.listdir(BILI_TEMP_DIR):
            if bvid in f and f.endswith('.srt'):
                subtitle_file = os.path.join(BILI_TEMP_DIR, f)
                break
        
        if subtitle_file:
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                content = f.read()
            os.remove(subtitle_file)
            return content
        
        return None
        
    except Exception as e:
        print(f"下载字幕失败: {e}")
        return None


def run_bilibili_task(task_id):
    """执行B站监控任务"""
    task = MonitorTask.query.get(task_id)
    if not task or task.platform != 'bilibili':
        return {"error": "任务不存在或平台不匹配"}
    
    # 获取账号Cookie
    account = MonitorAccount.query.get(task.account_id)
    cookie_value = account.cookie if account else None
    
    print(f"开始获取UP主视频: {task.target_value}")
    
    # 使用Playwright获取视频
    videos = get_up_videos_playwright(task.target_value)
    
    if not videos:
        return {"error": "无法获取视频列表", "videos": 0, "try": "playwright"}
    
    print(f"获取到 {len(videos)} 个视频")
    
    results = []
    task.last_run = datetime.utcnow()
    db.session.commit()
    
    for video in videos[:5]:
        bvid = video.get('bvid')
        title = video.get('title')
        url = video.get('url')
        
        if not bvid:
            continue
        
        # 检查是否已存在
        existing = MonitorContent.query.filter_by(
            task_id=task_id, url=url
        ).first()
        
        if existing:
            continue
        
        # 下载字幕
        subtitle_content = download_subtitle(bvid, cookie_value)
        
        # 保存内容
        content = MonitorContent(
            task_id=task_id,
            content_type='video',
            title=title,
            content=subtitle_content or '',
            url=url,
            publish_time=datetime.utcnow(),
            fetch_time=datetime.utcnow(),
            status='pending' if subtitle_content else 'error'
        )
        db.session.add(content)
        results.append({
            'bvid': bvid,
            'title': title,
            'subtitle': bool(subtitle_content)
        })
    
    db.session.commit()
    
    return {
        "task_id": task_id,
        "videos_found": len(videos),
        "new_videos": len(results),
        "results": results
    }
