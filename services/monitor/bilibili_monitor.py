"""
B站监控服务 - 使用RSSHub
"""
import os
import json
import re
import requests
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree
from models import db
from models.monitor import MonitorAccount, MonitorTask, MonitorContent

# 东八区时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

def get_now():
    """获取当前东八区时间"""
    return datetime.now(SHANGHAI_TZ)


def fetch_article_content(url: str, platform: str = '') -> str:
    """
    获取财经资讯正文内容
    
    Args:
        url: 文章URL
        platform: 平台标识
    
    Returns:
        正文内容，如果获取失败返回空字符串
    """
    if not url:
        return ''
    
    # 根据平台选择不同的获取方式
    try:
        # 财联社 cls.cn
        if 'cls.cn' in url:
            return _fetch_cls_content(url)
        # 东方财富 eastmoney.com
        elif 'eastmoney.com' in url:
            return _fetch_eastmoney_content(url)
        # 华尔街见闻 wallstreetcn.com
        elif 'wallstreetcn.com' in url:
            return _fetch_wallstreet_content(url)
        # 新浪财经 sina.com.cn
        elif 'sina.com.cn' in url:
            return _fetch_sina_content(url)
        # 证券时报 stcn.com
        elif 'stcn.com' in url:
            return _fetch_stcn_content(url)
        # 第一财经 yicai.com
        elif 'yicai.com' in url:
            return _fetch_yicai_content(url)
        # 财经网 cjjing.com
        elif 'cjjing' in url or 'caijing.com.cn' in url:
            return _fetch_caijing_content(url)
        else:
            # 通用方式：尝试直接获取
            return _fetch_generic_content(url)
    except Exception as e:
        print(f"获取正文失败: {url}, error: {e}")
        return ''


def _fetch_cls_content(url: str) -> str:
    """获取财联社正文"""
    try:
        # 从URL提取ID: https://www.cls.cn/detail/123456 或 https://api3.cls.cn/share/article/123456
        match = re.search(r'/detail/(\d+)', url)
        if not match:
            # 尝试 /article/ 格式
            match = re.search(r'/article/(\d+)', url)
        if not match:
            return ''
        
        article_id = match.group(1)
        api_url = f"https://www.cls.cn/nodeapi/updateTelegraph?app=CailianpressWeb&os=web&sv=7.7.5"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.cls.cn/',
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ''
        
        data = response.json()
        subjects = data.get('data', {}).get('subjects', []) if isinstance(data.get('data'), dict) else []
        
        for item in subjects:
            if str(item.get('id')) == article_id:
                # 优先使用content字段，如果没有则使用body
                content = item.get('content') or item.get('body') or item.get('summary', '')
                # 清理HTML标签
                content = re.sub(r'<[^>]+>', '', content)
                # 清理多余空白
                content = re.sub(r'\s+', ' ', content).strip()
                return content
        
        return ''
    except Exception as e:
        print(f"获取财联社正文失败: {e}")
        return ''


def _fetch_eastmoney_content(url: str) -> str:
    """获取东方财富正文"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://stock.eastmoney.com/',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ''
        
        # 尝试从HTML中提取正文
        html = response.text
        
        # 尝试提取article-content (普通文章)
        match = re.search(r'<div class="article-content[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            content = match.group(1)
            content = re.sub(r'<[^>]+>', '', content)
            content = re.sub(r'\s+', ' ', content).strip()
            if len(content) > 50:
                return content
        
        # 尝试提取id=ctx-content (个股研报)
        match = re.search(r'<div id="ctx-content"[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            content = match.group(1)
            content = re.sub(r'<[^>]+>', '', content)
            content = re.sub(r'\s+', ' ', content).strip()
            if len(content) > 50:
                return content
        
        # 尝试其他方式
        match = re.search(r'<div id="Content"[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            content = match.group(1)
            content = re.sub(r'<[^>]+>', '', content)
            content = re.sub(r'\s+', ' ', content).strip()
            return content
        
        return ''
    except Exception as e:
        print(f"获取东方财富正文失败: {e}")
        return ''


def _fetch_wallstreet_content(url: str) -> str:
    """获取华尔街见闻正文"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://wallstreetcn.com/',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ''
        
        html = response.text
        
        # 尝试提取正文
        match = re.search(r'<article[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</article>', html, re.DOTALL)
        if match:
            content = match.group(1)
            content = re.sub(r'<[^>]+>', '', content)
            content = re.sub(r'\s+', ' ', content).strip()
            return content
        
        return ''
    except Exception as e:
        print(f"获取华尔街见闻正文失败: {e}")
        return ''


def _fetch_sina_content(url: str) -> str:
    """获取新浪财经正文"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ''
        
        html = response.text
        
        # 尝试提取正文
        match = re.search(r'<div class="article-content[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            content = match.group(1)
            content = re.sub(r'<[^>]+>', '', content)
            content = re.sub(r'\s+', ' ', content).strip()
            return content
        
        return ''
    except Exception as e:
        print(f"获取新浪财经正文失败: {e}")
        return ''


def _fetch_stcn_content(url: str) -> str:
    """获取证券时报正文"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.stcn.com/',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ''
        
        html = response.text
        
        # 尝试提取正文
        match = re.search(r'<div class="article-text[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            content = match.group(1)
            content = re.sub(r'<[^>]+>', '', content)
            content = re.sub(r'\s+', ' ', content).strip()
            return content
        
        return ''
    except Exception as e:
        print(f"获取证券时报正文失败: {e}")
        return ''


def _fetch_yicai_content(url: str) -> str:
    """获取第一财经正文"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.yicai.com/',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ''
        
        html = response.text
        
        # 尝试提取正文
        match = re.search(r'<div class="article-content[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            content = match.group(1)
            content = re.sub(r'<[^>]+>', '', content)
            content = re.sub(r'\s+', ' ', content).strip()
            return content
        
        return ''
    except Exception as e:
        print(f"获取第一财经正文失败: {e}")
        return ''


def _fetch_caijing_content(url: str) -> str:
    """获取财经网正文"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.caijing.com.cn/',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ''
        
        html = response.text
        
        # 尝试提取正文
        match = re.search(r'<div class="article-text[^>]*>(.*?)</div>', html, re.DOTALL)
        if match:
            content = match.group(1)
            content = re.sub(r'<[^>]+>', '', content)
            content = re.sub(r'\s+', ' ', content).strip()
            return content
        
        return ''
    except Exception as e:
        print(f"获取财经网正文失败: {e}")
        return ''


def _fetch_generic_content(url: str) -> str:
    """通用方式获取正文"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ''
        
        html = response.text
        
        # 尝试提取常见正文容器
        patterns = [
            r'<article[^>]*>(.*?)</article>',
            r'<div class="content[^"]*">(.*?)</div>',
            r'<div class="article[^"]*">(.*?)</div>',
            r'<div id="article-content[^"]*"(.*?)</div>',
            r'<div class="text[^"]*">(.*?)</div>',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1)
                content = re.sub(r'<[^>]+>', '', content)
                content = re.sub(r'\s+', ' ', content).strip()
                if len(content) > 100:  # 确保内容有一定长度
                    return content
        
        return ''
    except Exception as e:
        print(f"通用获取正文失败: {e}")
        return ''

# RSSHub地址
RSSHUB_BASE = 'http://localhost:1200'

# 路由映射 - 将前端路由转换为RSSHub路由
ROUTE_MAP = {
    # UP主相关
    '/bilibili/user/video/:uid': '/bilibili/user/video/{uid}',
    '/bilibili/user/dynamic/:uid': '/bilibili/user/dynamic/{uid}',
    '/bilibili/user/article/:uid': '/bilibili/user/article/{uid}',
    '/bilibili/user/coin/:uid': '/bilibili/user/coin/{uid}',
    '/bilibili/user/fav/:uid': '/bilibili/user/fav/{uid}',
    '/bilibili/user/channel/:uid/:channelid': '/bilibili/user/channel/{uid}/{channelid}',
    '/bilibili/user/collection/:uid/:coverId': '/bilibili/user/collection/{uid}/{coverId}',
    '/bilibili/user/followers/:uid': '/bilibili/user/followers/{uid}',
    '/bilibili/user/followings/:uid': '/bilibili/user/followings/{uid}',
    '/bilibili/user/followings/video/:uid': '/bilibili/user/followings/video/{uid}',
    '/bilibili/user/followings/article/:uid': '/bilibili/user/followings/article/{uid}',
    # 分区
    '/bilibili/partion/:tid': '/bilibili/partion/{tid}',
    '/bilibili/partion/ranking/:tid/:days': '/bilibili/partion/ranking/{tid}/{days}',
    # 番剧
    '/bilibili/bangumi/media/:mediaid': '/bilibili/bangumi/media/{mediaid}',
    # 直播
    '/bilibili/live-room/:roomid': '/bilibili/live-room/{roomid}',
    '/bilibili/live-area/:areaid': '/bilibili/live-area/{areaid}',
    # 热门
    '/bilibili/popular/all': '/bilibili/popular/all',
    '/bilibili/popular/series/:pn': '/bilibili/popular/series/{pn}',
    '/bilibili/popular/history': '/bilibili/popular/history',
    '/bilibili/ranking/:type': '/bilibili/ranking/{type}',
    # 搜索
    '/bilibili/search/:keyword': '/bilibili/search/keyword/{keyword}',
    '/bilibili/vsearch/:keyword': '/bilibili/vsearch/keyword/{keyword}',
    # 热搜
    '/bilibili/hot-search': '/bilibili/hot-search',
    '/bilibili/hot/:category': '/bilibili/hot/{category}',
    # 视频
    '/bilibili/video/danmaku/:bvid': '/bilibili/video/danmaku/{bvid}',
    '/bilibili/watchlater': '/bilibili/watchlater',
    # 音频
    '/bilibili/audio/:id': '/bilibili/audio/{id}',
    # 专栏
    '/bilibili/link/news/:type': '/bilibili/link/news/{type}',
    # 每周必看
    '/bilibili/precious': '/bilibili/precious',
}


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
            '/home/clawdbot/.openclaw/workspace/Fund_backend/venv/bin/yt-dlp',
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


def run_bilibili_task(task_id, session=None):
    """执行B站监控任务 - 使用RSSHub"""
    from models import db
    from models.monitor.models import MonitorLog
    
    if session is None:
        session = db.session
    
    task = session.query(MonitorTask).get(task_id)
    if not task:
        return {"error": "任务不存在"}
    
    # 允许所有支持的平台
    supported_platforms = ['bilibili', 'gelonghui', 'jin10', 'wallstreetcn', 'cls', 'caijing', 'eastmoney']
    if task.platform not in supported_platforms:
        return {"error": f"不支持的平台: {task.platform}"}
    
    # 详细日志：任务信息
    log = MonitorLog(task_id=task_id, level='INFO', 
        message=f'📡 任务: {task.task_name} | 路由: {task.rss_route}')
    session.add(log)
    
    # 获取路由参数
    route_params = task.route_params or {}
    
    log = MonitorLog(task_id=task_id, level='INFO', 
        message=f'🔧 参数: {route_params}')
    session.add(log)
    
    # 构建RSSHub URL
    rss_route = task.rss_route
    route_template = ROUTE_MAP.get(rss_route, rss_route)
    
    # 替换参数 - 支持 :key 和 {key} 两种格式，同时处理可选参数
    url_path = route_template
    for key, value in route_params.items():
        if value:  # 只替换有值的参数
            url_path = url_path.replace(f':{key}', str(value))
            url_path = url_path.replace(f'{{{key}}}', str(value))
    
    # 清理未替换的可选参数占位符（如 {days}）
    import re
    url_path = re.sub(r'\{[a-zA-Z_]+\}', '', url_path)
    # 清理多余的斜杠
    url_path = re.sub(r'/+', '/', url_path)
    # 清理末尾的斜杠
    if url_path.endswith('/'):
        url_path = url_path.rstrip('/')
    
    rss_url = f"{RSSHUB_BASE}{url_path}"
    
    log = MonitorLog(task_id=task_id, level='INFO', 
        message=f'🌐 RSSHub URL: {rss_url}')
    session.add(log)
    session.commit()
    
    log = MonitorLog(task_id=task_id, level='INFO', 
        message=f'📡 准备请求RSSHub...')
    session.add(log)
    session.commit()
    
    try:
        # 获取RSS数据
        log = MonitorLog(task_id=task_id, level='INFO', 
            message=f'⏳ 正在请求RSSHub...')
        session.add(log)
        session.commit()
        
        response = requests.get(rss_url, timeout=30)
        
        log = MonitorLog(task_id=task_id, level='INFO', 
            message=f'📥 响应状态: {response.status_code}')
        session.add(log)
        session.commit()
        
        if response.status_code != 200:
            log = MonitorLog(task_id=task_id, level='ERROR', 
                message=f'❌ RSSHub返回错误状态码')
            session.add(log)
            session.commit()
            return {"error": f"HTTP {response.status_code}", "new_videos": 0}
        
        # 解析XML
        root = ElementTree.fromstring(response.content)
        
        # 获取items
        items = root.findall('.//item')
        if not items:
            log = MonitorLog(task_id=task_id, level='WARNING', 
                message=f'⚠️ 未获取到任何内容')
            session.add(log)
            session.commit()
            return {"error": "未获取到任何内容", "new_videos": 0}
        
        log = MonitorLog(task_id=task_id, level='INFO', 
            message=f'📊 获取到 {len(items)} 个原始内容')
        session.add(log)
        session.commit()
        
        results = []
        task.last_run_at = get_now()
        session.commit()
        
        saved_count = 0
        skipped_count = 0
        
        # 获取配置的最大保存数量（默认20条）
        max_items = task.max_results or 20
        for item in items[:max_items]:
            title = item.findtext('title', '')
            link = item.findtext('link', '')
            pub_date = item.findtext('pubDate', '')
            author = item.findtext('author', '')
            # 获取RSS中的description字段（对于财经类通常包含正文内容）
            rss_description = item.findtext('description', '')
            
            if not link:
                continue
            
            # 检查是否已存在
            existing = session.query(MonitorContent).filter_by(
                task_id=task_id, url=link
            ).first()
            
            if existing:
                skipped_count += 1
                continue
            
            # 对于B站平台：先尝试获取字幕作为正文
            subtitle_text = None
            if task.platform == 'bilibili':
                try:
                    account_cookie = None
                    if task.account_id:
                        account = session.query(MonitorAccount).get(task.account_id)
                        if account and account.cookie:
                            account_cookie = account.cookie
                    
                    # 调用API下载字幕
                    if account_cookie:
                        from routes.monitor.api import download_subtitle
                        subtitle_text = download_subtitle(link, account_cookie)
                except Exception as e:
                    print(f"获取字幕失败: {e}")
            
            # 根据平台设置正文内容
            if subtitle_text:
                # B站优先使用字幕
                content_text = subtitle_text[:5000]
            elif task.platform in ['cls', 'caijing', 'eastmoney', 'wallstreetcn', 'jin10', 'gelonghui']:
                # 财经类平台使用RSS description
                content_text = rss_description if rss_description else pub_date
            else:
                # 其他平台使用description或pub_date
                content_text = rss_description if rss_description else pub_date
            
            # 保存内容
            content = MonitorContent(
                task_id=task_id,
                platform=task.platform,
                title=title,
                url=link,
                author=author or '',
                description=content_text or '',
                publish_time=get_now()
            )
            session.add(content)
            session.flush()  # 获取content.id
            
            # 对于财经类平台，如果RSS的description太短，尝试获取完整正文
            # eastmoney个股研报比较特殊，RSS返回的是表格而非正文，需要特殊处理
            should_fetch = False
            if task.platform in ['cls', 'caijing', 'eastmoney', 'wallstreetcn', 'jin10', 'gelonghui']:
                # eastmoney的个股研报(/report/stock)RSS返回的是表格，需要获取正文
                if task.platform == 'eastmoney' and '/report/stock' in task.rss_route:
                    should_fetch = True
                elif not rss_description or len(rss_description) < 100:
                    should_fetch = True
                
                if should_fetch:
                    try:
                        article_content = fetch_article_content(link, task.platform)
                        if article_content:
                            content.description = article_content[:5000]
                            print(f"✅ 补充正文: {title[:30]}...")
                    except Exception as e:
                        print(f"获取正文失败: {e}")
            
            # 保存字幕到subtitle_content字段（B站已获取的不要再重复获取）
            if task.platform == 'bilibili' and subtitle_text:
                content.subtitle_content = subtitle_text[:5000]
            
            results.append({
                'title': title,
                'link': link
            })
            saved_count += 1
            
            # 详细日志：保存的每个内容
            title_short = title[:30] + '...' if len(title) > 30 else title
            log = MonitorLog(task_id=task_id, level='INFO', 
                message=f'✅ 新增: {title_short}')
            session.add(log)
        
        session.commit()
        
        # 详细日志：保存结果汇总
        log = MonitorLog(task_id=task_id, level='INFO', 
            message=f'📝 保存结果: 新增 {saved_count} 条, 跳过 {skipped_count} 条(已存在)')
        session.add(log)
        session.commit()
        
        return {
            "task_id": task_id,
            "videos_found": len(items),
            "new_videos": len(results),
            "results": results
        }
        
    except Exception as e:
        print(f"RSSHub请求失败: {e}")
        import traceback
        traceback.print_exc()
        log = MonitorLog(task_id=task_id, level='ERROR', 
            message=f'❌ RSSHub请求失败: {str(e)}')
        session.add(log)
        session.commit()
        return {"error": str(e), "new_videos": 0}
