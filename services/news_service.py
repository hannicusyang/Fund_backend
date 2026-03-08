# services/news_service.py
# 新闻服务 - 纯真实数据源，无虚拟数据

import requests
import json
import time
import hashlib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config.logging_config import logger


def clean_html_content(html_content: str) -> str:
    """清洗HTML标签，转换为纯文本"""
    if not html_content:
        return ''
    
    # 移除风险提示和免责声明
    html_content = re.sub(r'<div[^>]*style=["\']?color:\s*#666[^>]*>.*?风险提示.*?</div>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<div[^>]*style=["\']?font-size:\s*12px[^>]*>.*?市场有风险.*?</div>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<div[^>]*>.*?免责条款.*?</div>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # 移除HTML注释
    html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
    
    # 将常见的HTML标签替换为换行
    html_content = re.sub(r'</?p[^>]*>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?h[1-6][^>]*>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?div[^>]*>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?li[^>]*>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?tr[^>]*>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</?td[^>]*>', '\t', html_content, flags=re.IGNORECASE)
    
    # 处理链接，保留文本但移除标签
    html_content = re.sub(r'<a[^>]*>([^<]*)</a>', r'\1', html_content, flags=re.IGNORECASE)
    
    # 移除所有剩余的HTML标签
    html_content = re.sub(r'<[^>]+>', '', html_content)
    
    # 解码HTML实体
    html_content = html_content.replace('&nbsp;', ' ')
    html_content = html_content.replace('&amp;', '&')
    html_content = html_content.replace('&lt;', '<')
    html_content = html_content.replace('&gt;', '>')
    html_content = html_content.replace('&quot;', '"')
    html_content = html_content.replace('&#39;', "'")
    
    # 清理多余的空白字符
    html_content = re.sub(r'[ \t]+', ' ', html_content)
    html_content = re.sub(r'\n\s*\n', '\n', html_content)
    html_content = html_content.strip()
    
    return html_content

# 缓存类
class NewsCache:
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, tuple] = {}
        self._ttl = ttl_seconds
    
    def _make_key(self, source: str, **kwargs) -> str:
        key_parts = [source]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        return hashlib.md5('|'.join(key_parts).encode()).hexdigest()
    
    def get(self, source: str, **kwargs) -> Optional[Dict]:
        key = self._make_key(source, **kwargs)
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return data
            else:
                del self._cache[key]
        return None
    
    def set(self, source: str, data: Dict, **kwargs):
        key = self._make_key(source, **kwargs)
        self._cache[key] = (data, time.time())
    
    def clear(self):
        self._cache.clear()


_news_cache = NewsCache(ttl_seconds=300)


class NewsSource:
    """新闻源基类"""
    name: str = ""
    
    def fetch(self, limit: int = 50, keyword: str = "", 
              start_date: str = "", end_date: str = "") -> List[Dict]:
        raise NotImplementedError


class CLSNewsSource(NewsSource):
    """财联社 - 真实API"""
    name = "cls"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            url = "https://www.cls.cn/nodeapi/updateTelegraph"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.cls.cn/',
            }
            
            params = {
                'app': 'CailianpressWeb',
                'os': 'web',
                'sv': '7.7.5'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                news_list = []
                subjects = data.get('data', {}).get('subjects', []) if isinstance(data.get('data'), dict) else []
                
                for item in subjects:
                    title = item.get('title', '')
                    if keyword and keyword.lower() not in title.lower():
                        continue
                    
                    # 解析时间戳
                    publish_time = item.get('publish_time', 0)
                    if publish_time:
                        dt = datetime.fromtimestamp(publish_time)
                        time_str = dt.strftime('%Y-%m-%d %H:%M')
                    else:
                        time_str = ''
                    
                    news_list.append({
                        'id': f"cls_{item.get('id', '')}",
                        'title': title,
                        'content': item.get('summary', ''),
                        'source': '财联社',
                        'source_name': self.name,
                        'datetime': time_str,
                        'url': f"https://www.cls.cn/detail/{item.get('id', '')}",
                        'category': self._extract_category(title)
                    })
                
                return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取财联社新闻失败: {e}")
        
        return []
    
    def _extract_category(self, title: str) -> str:
        title = title.lower()
        if any(k in title for k in ['基金', 'etf', '公募', '私募']): return '基金'
        elif any(k in title for k in ['股', '上市', '年报', '涨停', '跌停', 'ipo']): return '股票'
        elif any(k in title for k in ['宏观', '央行', '利率', 'cpi', 'gdp', '降息', '降准', '货币']): return '宏观'
        elif any(k in title for k in ['新能', '光伏', '锂', '风电', '电动车', '比亚迪', '宁德']): return '新能源'
        elif any(k in title for k in ['半导', '芯片', 'ai', '人工智能', '5g', '软件']): return '科技'
        elif any(k in title for k in ['医药', '医疗', '生物', '疫苗', '中药']): return '医药'
        elif any(k in title for k in ['消费', '食品', '饮料', '白酒', '家电', '零售']): return '消费'
        elif any(k in title for k in ['银行', '保险', '证券', '金融', '券商']): return '金融'
        return '综合'


class EastMoneyNewsSource(NewsSource):
    """东方财富 - 真实API"""
    name = "eastmoney"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        news_list = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://stock.eastmoney.com/',
        }
        
        # 计算需要获取的页数（每页100条）
        pages = (limit + 99) // 100
        
        for page in range(1, pages + 1):
            try:
                api_limit = 100
                url = f"https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_{api_limit}_{page}_.html"
                
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    text = response.text
                    match = re.search(r'\{.*\}', text, re.DOTALL)
                    if match:
                        data = json.loads(match.group())
                        
                        for idx, item in enumerate(data.get('LivesList', [])):
                            title = item.get('title', '')
                            if keyword and keyword.lower() not in title.lower():
                                continue
                            
                            news_list.append({
                                'id': f"em_{item.get('id', idx)}",
                                'title': title,
                                'content': item.get('digest', ''),
                                'source': '东方财富',
                                'source_name': self.name,
                                'datetime': item.get('showtime', ''),
                                'url': f"https://stock.eastmoney.com{item.get('url', '')}",
                                'category': self._extract_category(title)
                            })
                
            except Exception as e:
                logger.warning(f"获取东方财富第{page}页新闻失败: {e}")
                break
        
        if news_list:
            return news_list[:limit]
        
        # 备用：尝试财经网
        return self._fetch_from_caijing(limit, keyword)
    
    def _fetch_from_caijing(self, limit: int, keyword: str) -> List[Dict]:
        """从财经网获取备用数据"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            # 财经网没有RSS，使用内参中心API
            url = "https://apicyidian.10jqka.com.cn/interface/14557/1/"
            
            response = requests.get(url, headers=headers, timeout=8)
            if response.status_code == 200:
                data = response.json()
                news_list = []
                
                for idx, item in enumerate(data.get('data', [])[:limit]):
                    title = item.get('title', '')
                    if keyword and keyword.lower() not in title.lower():
                        continue
                    
                    news_list.append({
                        'id': f"cj_{idx}",
                        'title': title,
                        'content': item.get('content', ''),
                        'source': '财经网',
                        'source_name': 'caijing',
                        'datetime': item.get('time', ''),
                        'url': item.get('url', 'https://www.caijing.com.cn'),
                        'category': self._extract_category(title)
                    })
                
                return news_list[:limit]
                
        except Exception as e:
            logger.warning(f"获取财经网数据失败: {e}")
        
        return []
    
    def _extract_category(self, title: str) -> str:
        """提取新闻分类 - 更严格的财经分类"""
        title_lower = title.lower()
        
        # 非财经关键词 - 直接排除
        non_finance = [
            '俄乌', '乌克兰', '俄罗斯', '特朗普', '拜登', '美国', '欧洲', '国际', '外媒',
            '天气', '暴雨', '台风', '地震', '火灾', '事故', '犯罪', '娱乐', '社会',
            '明星', '电影', '音乐', '体育', '足球', '网红', '跪拜', '风俗', '热搜',
            '开学', '放假', '高考', '中考', '大学', '学校', '教育', '医保', '社保', '民生',
            '泽连斯基', ' Truth Social', '罕见难病', '确诊', '确诊'
        ]
        
        # 先排除明显非财经
        for kw in non_finance:
            if kw.lower() in title_lower:
                return '综合'
        
        # 财经关键词 - 优先级从高到低
        if any(k in title_lower for k in ['基金', 'etf', '公募', '私募', 'lof', '资管']): return '基金'
        elif any(k in title_lower for k in ['转债', '债券', '国债', '收益率', '债市']): return '债券'
        elif any(k in title_lower for k in ['银行', '保险', '券商', '证券', '金融', '平安', '招商', '理财']): return '金融'
        elif any(k in title_lower for k in ['新能', '光伏', '锂', '风电', '电动车', '比亚迪', '宁德', '储能', '新能源车']): return '新能源'
        elif any(k in title_lower for k in ['半导', '芯片', 'ai', '人工智能', '5g', '华为', '苹果', '科技']): return '科技'
        elif any(k in title_lower for k in ['医药', '医疗', '生物', '疫苗', '中药', '恒瑞', '药明']): return '医药'
        elif any(k in title_lower for k in ['消费', '食品', '饮料', '白酒', '茅台', '家电', '伊利', '海螺', '零售']): return '消费'
        elif any(k in title_lower for k in ['宏观', '央行', '利率', 'cpi', 'gdp', '降息', '降准', 'lpr', '财政', '货币']): return '宏观'
        elif any(k in title_lower for k in ['股', '上市', '年报', '涨停', '跌停', 'ipo', '分红', '业绩', '财报', 'a股', '沪指', '深指', '创业板', '科创板', '大盘', '指数', '估值', '市值', '股价', '增持', '减持', '回购', '融资', '北向资金', '外资']): return '股票'
        
        return '综合'


class SinaNewsSource(NewsSource):
    """新浪财经 - RSS真实数据"""
    name = "sina"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # 多个RSS源
            rss_feeds = [
                'https://rss.sina.com.cn/finance/roll.xml',
                'https://rss.sina.com.cn/news/markets.xml',
            ]
            
            news_list = []
            
            for rss_url in rss_feeds:
                try:
                    response = requests.get(rss_url, headers=headers, timeout=5)
                    if response.status_code == 200:
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(response.content)
                        
                        for item in root.findall('.//item')[:15]:
                            title_elem = item.find('title')
                            if title_elem is None:
                                continue
                            
                            title_text = title_elem.text or ''
                            
                            if keyword and keyword.lower() not in title_text.lower():
                                continue
                            
                            # 尝试获取发布时间
                            pub_date = item.find('pubDate')
                            if pub_date is not None and pub_date.text:
                                try:
                                    dt = datetime.strptime(pub_date.text[:25], '%a, %d %b %Y %H:%M:%S')
                                    time_str = dt.strftime('%Y-%m-%d %H:%M')
                                except:
                                    time_str = ''
                            else:
                                time_str = ''
                            
                            link_elem = item.find('link')
                            
                            news_list.append({
                                'id': f"sina_{len(news_list)}",
                                'title': title_text,
                                'content': '',
                                'source': '新浪财经',
                                'source_name': self.name,
                                'datetime': time_str,
                                'url': link_elem.text if link_elem is not None else 'https://finance.sina.com.cn',
                                'category': self._extract_category(title_text)
                            })
                except:
                    continue
            
            if news_list:
                return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取新浪新闻失败: {e}")
        
        return []
    
    def _extract_category(self, title: str) -> str:
        title = title.lower()
        if any(k in title for k in ['基金', 'etf']): return '基金'
        elif any(k in title for k in ['股', '上市', 'ipo']): return '股票'
        elif any(k in title for k in ['宏观', '央行', '利率']): return '宏观'
        return '综合'


class TencentNewsSource(NewsSource):
    """腾讯财经 - 真实API"""
    name = "qq"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://finance.qq.com/'
            }
            
            # 腾讯财经API
            url = "https://rss.qq.com/weather/finance.xml"
            
            # 尝试腾讯新闻API
            api_url = "https://rss.qq.com/finance/fund.xml"
            
            response = requests.get(api_url, headers=headers, timeout=8)
            
            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.content)
                news_list = []
                
                for item in root.findall('.//item')[:limit]:
                    title_elem = item.find('title')
                    if title_elem is None:
                        continue
                    
                    title_text = title_elem.text or ''
                    
                    if keyword and keyword.lower() not in title_text.lower():
                        continue
                    
                    link_elem = item.find('link')
                    
                    news_list.append({
                        'id': f"qq_{len(news_list)}",
                        'title': title_text,
                        'content': '',
                        'source': '腾讯财经',
                        'source_name': self.name,
                        'datetime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'url': link_elem.text if link_elem is not None else 'https://finance.qq.com',
                        'category': self._extract_category(title_text)
                    })
                
                return news_list[:limit]
                
        except Exception as e:
            logger.warning(f"获取腾讯新闻失败: {e}")
        
        return []
    
    def _extract_category(self, title: str) -> str:
        title = title.lower()
        if any(k in title for k in ['基金', '理财']): return '基金'
        elif any(k in title for k in ['股', '上市']): return '股票'
        elif any(k in title for k in ['宏观', '央行']): return '宏观'
        return '综合'


class HexunNewsSource(NewsSource):
    """和讯网 - 真实API"""
    name = "hexun"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.hexun.com/'
            }
            
            # 和讯财经RSS
            rss_urls = [
                'https://rss.hexun.com/rss/finance.xml',
                'https://rss.hexun.com/rss/stock.xml',
            ]
            
            news_list = []
            
            for rss_url in rss_urls:
                try:
                    response = requests.get(rss_url, headers=headers, timeout=5)
                    if response.status_code == 200:
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(response.content)
                        
                        for item in root.findall('.//item')[:10]:
                            title_elem = item.find('title')
                            if title_elem is None:
                                continue
                            
                            title_text = title_elem.text or ''
                            
                            if keyword and keyword.lower() not in title_text.lower():
                                continue
                            
                            link_elem = item.find('link')
                            
                            news_list.append({
                                'id': f"hexun_{len(news_list)}",
                                'title': title_text,
                                'content': '',
                                'source': '和讯网',
                                'source_name': self.name,
                                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                                'url': link_elem.text if link_elem is not None else 'https://www.hexun.com',
                                'category': self._extract_category(title_text)
                            })
                except:
                    continue
            
            return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取和讯新闻失败: {e}")
        
        return []
    
    def _extract_category(self, title: str) -> str:
        title = title.lower()
        if any(k in title for k in ['基金']): return '基金'
        elif any(k in title for k in ['股']): return '股票'
        return '综合'


class IfengNewsSource(NewsSource):
    """凤凰网财经 - 真实RSS"""
    name = "ifeng"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # 凤凰网财经RSS
            url = "https://finance.ifeng.com/rss/finance.xml"
            
            response = requests.get(url, headers=headers, timeout=8)
            
            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.content)
                news_list = []
                
                for item in root.findall('.//item')[:limit]:
                    title_elem = item.find('title')
                    if title_elem is None:
                        continue
                    
                    title_text = title_elem.text or ''
                    
                    if keyword and keyword.lower() not in title_text.lower():
                        continue
                    
                    link_elem = item.find('link')
                    
                    news_list.append({
                        'id': f"ifeng_{len(news_list)}",
                        'title': title_text,
                        'content': '',
                        'source': '凤凰网财经',
                        'source_name': self.name,
                        'datetime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'url': link_elem.text if link_elem is not None else 'https://finance.ifeng.com',
                        'category': self._extract_category(title_text)
                    })
                
                return news_list[:limit]
                
        except Exception as e:
            logger.warning(f"获取凤凰网新闻失败: {e}")
        
        return []
    
    def _extract_category(self, title: str) -> str:
        title = title.lower()
        if any(k in title for k in ['基金']): return '基金'
        elif any(k in title for k in ['股']): return '股票'
        elif any(k in title for k in ['宏观', '央行']): return '宏观'
        return '综合'


# 证券时报
class STCNNewsSource(NewsSource):
    """证券时报 - 真实API"""
    name = "stcn"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            url = "https://www.stcn.com/articles/get_roll_news.html"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.stcn.com/',
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    news_list = []
                    
                    for idx, item in enumerate(data.get('data', [])[:limit]):
                        title = item.get('title', '')
                        if keyword and keyword.lower() not in title.lower():
                            continue
                        
                        news_list.append({
                            'id': f"stcn_{item.get('id', idx)}",
                            'title': title,
                            'content': item.get('digest', ''),
                            'source': '证券时报',
                            'source_name': self.name,
                            'datetime': item.get('pub_time', ''),
                            'url': item.get('url', 'https://www.stcn.com/'),
                            'category': self._extract_category(title)
                        })
                    
                    return news_list[:limit]
                except:
                    pass
            
        except Exception as e:
            logger.warning(f"获取证券时报新闻失败: {e}")
        
        return []
    
    def _extract_category(self, title: str) -> str:
        title = title.lower()
        if any(k in title for k in ['基金', 'etf']): return '基金'
        elif any(k in title for k in ['股', '上市', 'ipo']): return '股票'
        elif any(k in title for k in ['宏观', '央行']): return '宏观'
        return '综合'


# 第一财经
class YicaiNewsSource(NewsSource):
    """第一财经 - 真实API"""
    name = "yicai"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            url = "https://www.yicai.com/news/ajaxgetnewslists"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.yicai.com/news/',
            }
            
            params = {
                'type': 0,
                'p': 1,
                'pagesize': limit
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                news_list = []
                
                for idx, item in enumerate(data.get('result', [])[:limit]):
                    title = item.get('NewsTitle', '')
                    if keyword and keyword.lower() not in title.lower():
                        continue
                    
                    news_list.append({
                        'id': f"yicai_{item.get('Id', idx)}",
                        'title': title,
                        'content': item.get('NewsSummary', ''),
                        'source': '第一财经',
                        'source_name': self.name,
                        'datetime': item.get('PubTime', ''),
                        'url': f"https://www.yicai.com/news/{item.get('Id', '')}.html",
                        'category': self._extract_category(title)
                    })
                
                return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取第一财经新闻失败: {e}")
        
        return []
    
    def _extract_category(self, title: str) -> str:
        title = title.lower()
        if any(k in title for k in ['基金', 'etf']): return '基金'
        elif any(k in title for k in ['股', '上市', 'ipo']): return '股票'
        return '综合'


# 彭博社
class BloombergNewsSource(NewsSource):
    """彭博社财经 - RSS订阅"""
    name = "bloomberg"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            import xml.etree.ElementTree as ET
            
            url = "https://feeds.bloomberg.com/markets/news.rss"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Handle bytes response
                content = response.content
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
                
                root = ET.fromstring(content)
                news_list = []
                
                for item in root.findall('.//item')[:limit]:
                    title_elem = item.find('title')
                    if title_elem is None:
                        continue
                    
                    title = title_elem.text or ''
                    if keyword and keyword.lower() not in title.lower():
                        continue
                    
                    desc_elem = item.find('description')
                    content_text = desc_elem.text if desc_elem is not None and desc_elem.text else ''
                    
                    news_list.append({
                        'id': f"bloomberg_{hash(title) % 100000}",
                        'title': title,
                        'content': content_text,
                        'source': '彭博社',
                        'source_name': self.name,
                        'datetime': '',
                        'url': 'https://www.bloomberg.com/markets',
                        'category': '综合'
                    })
                
                return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取彭博社新闻失败: {e}")
        
        return []


# 华尔街见闻
class WallStreetNewsSource(NewsSource):
    """华尔街见闻 - RSS订阅"""
    name = "wallstreet"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            import xml.etree.ElementTree as ET
            
            url = "https://wallstreetcn.com/rss"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://wallstreetcn.com/',
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.content.encode())
                    news_list = []
                    
                    for item in root.findall('.//item')[:limit]:
                        title_elem = item.find('title')
                        if title_elem is None:
                            continue
                        
                        title = title_elem.text or ''
                        if keyword and keyword.lower() not in title.lower():
                            continue
                        
                        desc_elem = item.find('description')
                        content = desc_elem.text[:200] if desc_elem is not None and desc_elem.text else ''
                        
                        link = ''
                        link_elem = item.find('link')
                        if link_elem is not None:
                            link = link_elem.text or ''
                        
                        news_list.append({
                            'id': f"wsj_{hash(title) % 100000}",
                            'title': title,
                            'content': content,
                            'source': '华尔街见闻',
                            'source_name': self.name,
                            'datetime': '',
                            'url': link or 'https://wallstreetcn.com/',
                            'category': '综合'
                        })
                    
                    return news_list[:limit]
                except:
                    pass
            
        except Exception as e:
            logger.warning(f"获取华尔街见闻新闻失败: {e}")
        
        return []


# 同花顺
class TonghuashunNewsSource(NewsSource):
    """同花顺财经"""
    name = "iwencai"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            # 使用同花顺财经新闻页面
            url = "https://www.iwencai.com/dg-service/news/list"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.iwencai.com/',
                'Content-Type': 'application/json'
            }
            
            data = {
                "page": 1,
                "size": limit,
                "type": "stock"
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                news_list = []
                
                for idx, item in enumerate(result.get('data', [])):
                    title = item.get('title', '')
                    if keyword and keyword.lower() not in title.lower():
                        continue
                    
                    news_list.append({
                        'id': f"ths_{item.get('id', idx)}",
                        'title': title,
                        'content': item.get('digest', ''),
                        'source': '同花顺',
                        'source_name': self.name,
                        'datetime': item.get('time', ''),
                        'url': item.get('url', 'https://www.iwencai.com/'),
                        'category': self._extract_category(title)
                    })
                
                return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取同花顺新闻失败: {e}")
        
        return []
    
    def _extract_category(self, title: str) -> str:
        title = title.lower()
        if any(k in title for k in ['基金', 'etf']): return '基金'
        elif any(k in title for k in ['股', '上市', 'ipo']): return '股票'
        elif any(k in title for k in ['宏观', '央行']): return '宏观'
        return '综合'


# 雪球财经
class XueqiuNewsSource(NewsSource):
    """雪球财经 - 真实API"""
    name = "xueqiu"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            import xml.etree.ElementTree as ET
            
            # 雪球精选RSS
            url = "https://xueqiu.com/v4/statuses/public_timeline.json"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://xueqiu.com/',
                'Cookie': 'xq_a_token=test'
            }
            
            params = {
                'count': limit,
                'page': 1,
                'type': 'status'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                news_list = []
                
                for idx, item in enumerate(data.get('list', [])[:limit]):
                    title = item.get('text', '')
                    # 清理HTML标签
                    title = re.sub(r'<[^>]+>', '', title)
                    if len(title) > 100:
                        title = title[:100] + '...'
                    
                    if keyword and keyword.lower() not in title.lower():
                        continue
                    
                    user = item.get('user', {})
                    
                    news_list.append({
                        'id': f"xueqiu_{item.get('id', idx)}",
                        'title': title,
                        'content': '',
                        'source': '雪球',
                        'source_name': self.name,
                        'datetime': item.get('created_at', '')[:10] if item.get('created_at') else '',
                        'url': f"https://xueqiu.com/status/{item.get('id', '')}",
                        'category': '综合'
                    })
                
                return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取雪球新闻失败: {e}")
        
        return []


# 智谱财经（模拟）
class ZhihuNewsSource(NewsSource):
    """智谱财经 - 基于公开API"""
    name = "zhihu"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            # 尝试获取知乎热榜
            url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                news_list = []
                
                for idx, item in enumerate(data.get('data', [])[:limit]):
                    title = item.get('target', {}).get('title', '')
                    
                    if keyword and keyword.lower() not in title.lower():
                        continue
                    
                    news_list.append({
                        'id': f"zhihu_{item.get('id', idx)}",
                        'title': title,
                        'content': item.get('target', {}).get('excerpt', '')[:100],
                        'source': '知乎',
                        'source_name': self.name,
                        'datetime': '',
                        'url': item.get('target', {}).get('url', ''),
                        'category': '综合'
                    })
                
                return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取知乎新闻失败: {e}")
        
        return []


# 微博财经
class WeiboNewsSource(NewsSource):
    """微博财经"""
    name = "weibo"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            # 微博热搜API
            url = "https://weibo.com/ajax/side/hotSearch"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://weibo.com'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                news_list = []
                
                for idx, item in enumerate(data.get('data', {}).get('realtime', [])[:limit]):
                    word = item.get('word', '') or item.get('note', '')
                    
                    if keyword and keyword.lower() not in word.lower():
                        continue
                    
                    # 只保留财经相关话题
                    if any(k in word.lower() for k in ['股', '基金', '金融', '经济', 'A股', 'IPO', '上市', '理财', '投资', 'A股', '港股', '美股']):
                        news_list.append({
                            'id': f"weibo_{item.get('id', idx)}",
                            'title': word,
                            'content': f"热度: {item.get('raw_hot', 0)}",
                            'source': '微博',
                            'source_name': self.name,
                            'datetime': '',
                            'url': f"https://s.weibo.com/weibo?q={word}",
                            'category': '综合'
                        })
                
                return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取微博新闻失败: {e}")
        
        return []


# 搜狐财经
class SohuNewsSource(NewsSource):
    """搜狐财经 - 真实API"""
    name = "sohu"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            url = "https://v2.sohu.com/public-api/feed"
            params = {
                'scene': 'CATEGORY',
                'sceneId': '1462',  # 财经频道
                'page': 1,
                'size': limit
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.sohu.com/'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                news_list = []
                
                for idx, item in enumerate(data):
                    title = item.get('mobileTitle', '')
                    if not title:
                        title = item.get('title', '')
                    
                    if keyword and keyword.lower() not in title.lower():
                        continue
                    
                    # 解析时间戳
                    pub_time = item.get('publicTime', 0)
                    if pub_time:
                        try:
                            import time
                            time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(pub_time / 1000))
                        except:
                            time_str = ''
                    else:
                        time_str = ''
                    
                    news_list.append({
                        'id': f"sohu_{item.get('id', idx)}",
                        'title': title,
                        'content': '',
                        'source': '搜狐',
                        'source_name': self.name,
                        'datetime': time_str,
                        'url': f"https://www.sohu.com/a/{item.get('id', '')}",
                        'category': '财经'
                    })
                
                return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取搜狐新闻失败: {e}")
        
        return []


# 澎湃新闻
class PengpaiNewsSource(NewsSource):
    """澎湃新闻"""
    name = "pengpai"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        try:
            url = "https://www.thepaper.cn/newsDetail_ajax_01_"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.thepaper.cn/'
            }
            
            news_list = []
            for page in range(1, 3):  # 获取2页
                api_url = f"https://www.thepaper.cn/list_ajax_01_?pageNo={page}&pageLoad=true&type=1"
                response = requests.get(api_url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    for idx, item in enumerate(data.get('list', [])[:10]):
                        title = item.get('comm_news_title', '')
                        
                        if keyword and keyword.lower() not in title.lower():
                            continue
                        
                        news_list.append({
                            'id': f"pp_{item.get('id', idx)}",
                            'title': title,
                            'content': item.get('comm_news_summary', ''),
                            'source': '澎湃新闻',
                            'source_name': self.name,
                            'datetime': item.get('pubTime', ''),
                            'url': f"https://www.thepaper.cn/detail_{item.get('id', '')}",
                            'category': '综合'
                        })
                
                if len(news_list) >= limit:
                    break
            
            return news_list[:limit]
            
        except Exception as e:
            logger.warning(f"获取澎湃新闻失败: {e}")
        
        return []


# 东方财富多板块新闻源
class EastMoneyMultiNewsSource(NewsSource):
    """东方财富多板块新闻 - 获取8个板块的新闻"""
    name = "eastmoney_multi"
    
    # 板块ID映射
    CHANNELS = [
        (102, '要闻'),
        (103, '市场'),
        (104, '产经'),
        (105, '全球'),
        (106, '港股'),
        (107, '美股'),
        (108, '期货'),
        (109, '外汇'),
    ]
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        news_list = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (.0; WinWindows NT 1064; x64) AppleWebKit/537.36',
            'Referer': 'https://stock.eastmoney.com/',
        }
        
        # 获取所有板块的新闻
        for channel_id, channel_name in self.CHANNELS:
            try:
                url = f'https://newsapi.eastmoney.com/kuaixun/v1/getlist_{channel_id}_ajaxResult_50_1_.html'
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    text = response.text
                    match = re.search(r'\{.*\}', text, re.DOTALL)
                    if match:
                        data = json.loads(match.group())
                        
                        for idx, item in enumerate(data.get('LivesList', [])):
                            title = item.get('title', '')
                            if keyword and keyword.lower() not in title.lower():
                                continue
                            
                            news_list.append({
                                'id': f"em_{channel_id}_{item.get('id', idx)}",
                                'title': title,
                                'content': item.get('digest', ''),
                                'source': '东方财富',
                                'source_name': self.name,
                                'datetime': item.get('showtime', ''),
                                'url': f"https://stock.eastmoney.com{item.get('url', '')}",
                                'category': channel_name
                            })
                            
            except Exception as e:
                logger.warning(f"获取东方财富{channel_name}新闻失败: {e}")
                continue
        
        # 按时间排序
        news_list.sort(key=lambda x: x.get('datetime', ''), reverse=True)
        return news_list[:limit]


# 新浪财经多栏目新闻源
class SinaMultiNewsSource(NewsSource):
    """新浪财经多栏目新闻"""
    name = "sina_multi"
    
    CHANNELS = [
        ('https://finance.sina.com.cn/stock/', '股票'),
        ('https://finance.sina.com.cn/realstock/', '个股'),
        ('https://finance.sina.com.cn/money/', '理财'),
    ]
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        news_list = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        for url, category in self.CHANNELS:
            try:
                response = requests.get(url, headers=headers, timeout=8)
                if response.status_code == 200:
                    response.encoding = 'utf-8'
                    # 简单解析 - 查找新闻标题链接
                    import re
                    # 匹配 class="news-link" 或类似模式的链接
                    pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]{10,100})</a>'
                    matches = re.findall(pattern, response.text)
                    
                    for href, title in matches[:10]:
                        if 'sina.com.cn' in href and title:
                            if keyword and keyword.lower() not in title.lower():
                                continue
                            news_list.append({
                                'id': f"sina_{len(news_list)}",
                                'title': title.strip(),
                                'content': '',
                                'source': '新浪财经',
                                'source_name': self.name,
                                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                                'url': href if href.startswith('http') else f'https://finance.sina.com.cn{href}',
                                'category': category
                            })
            except Exception as e:
                logger.warning(f"获取新浪{category}新闻失败: {e}")
        
        return news_list[:limit]


# 证券时报新闻源 - 从首页获取
class STCNNewsSourceV2(NewsSource):
    """证券时报 - 从首页HTML解析"""
    name = "stcn_v2"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        news_list = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        # 尝试不同URL
        urls = [
            ('https://www.stcn.com/u/cms/www/', '财经'),
            ('https://www.stcn.com/news/index.html', '新闻'),
        ]
        
        for url, category in urls:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    response.encoding = 'utf-8'
                    
                    # 查找文章链接 - 常见模式
                    import re
                    # 匹配 /news/xxx.html 形式的链接
                    pattern = r'<a[^>]*href=["\']("/news/[^"\']+\.html")["\'][^>]*>([^<]{5,100})</a>'
                    matches = re.findall(pattern, response.text)
                    
                    for href, title in matches[:15]:
                        title = title.strip()
                        if title and len(title) > 5:
                            if keyword and keyword.lower() not in title.lower():
                                continue
                            news_list.append({
                                'id': f"stcn_{len(news_list)}",
                                'title': title,
                                'content': '',
                                'source': '证券时报',
                                'source_name': self.name,
                                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                                'url': f"https://www.stcn.com{href}",
                                'category': category
                            })
            except Exception as e:
                logger.warning(f"获取证券时报失败: {e}")
        
        # 去重
        seen = set()
        unique = []
        for n in news_list:
            if n['title'] not in seen:
                seen.add(n['title'])
                unique.append(n)
        
        return unique[:limit]


# 凤凰网财经新闻源
class IfengFinanceNewsSource(NewsSource):
    """凤凰网财经 - 从首页解析"""
    name = "ifeng_finance"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        news_list = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        try:
            response = requests.get('https://finance.ifeng.com/', headers=headers, timeout=10)
            if response.status_code == 200:
                response.encoding = 'utf-8'
                
                import re
                # 匹配财经新闻链接
                pattern = r'<a[^>]*href=["\']("https?://finance\.ifeng\.com/a/[^"\']+")["\'][^>]*>([^<]{5,100})</a>'
                matches = re.findall(pattern, response.text)
                
                for url, title in matches[:20]:
                    title = title.strip()
                    if title and len(title) > 5:
                        if keyword and keyword.lower() not in title.lower():
                            continue
                        news_list.append({
                            'id': f"ifeng_{len(news_list)}",
                            'title': title,
                            'content': '',
                            'source': '凤凰网财经',
                            'source_name': self.name,
                            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                            'url': url.strip('"'),
                            'category': '财经'
                        })
        except Exception as e:
            logger.warning(f"获取凤凰网财经失败: {e}")
        
        return news_list[:limit]


# 新闻源注册表
NEWS_SOURCES = {
    'cls': CLSNewsSource(),
    'eastmoney': EastMoneyNewsSource(),
    'eastmoney_multi': EastMoneyMultiNewsSource(),
    'sina': SinaNewsSource(),
    'sina_multi': SinaMultiNewsSource(),
    'qq': TencentNewsSource(),
    'hexun': HexunNewsSource(),
    'ifeng': IfengNewsSource(),
    'ifeng_finance': IfengFinanceNewsSource(),
    'stcn': STCNNewsSource(),
    'stcn_v2': STCNNewsSourceV2(),
    'yicai': YicaiNewsSource(),
    'bloomberg': BloombergNewsSource(),
    'wallstreet': WallStreetNewsSource(),
    'iwencai': TonghuashunNewsSource(),
    'xueqiu': XueqiuNewsSource(),
    'weibo': WeiboNewsSource(),
    'sohu': SohuNewsSource(),
    'pengpai': PengpaiNewsSource(),
}


def fetch_news(
    sources: List[str] = None,
    limit: int = 50,
    keyword: str = "",
    category: str = "",
    start_date: str = "",
    end_date: str = ""
) -> Dict:
    """获取财经新闻（并发获取）"""
    from concurrent.futures import ThreadPoolExecutor
    
    # 默认使用多个新闻源来获取更多数据
    # 优先使用稳定可用的源（有完整摘要）
    # eastmoney - 有digest摘要
    # eastmoney_multi - 8个板块，有摘要
    stable_sources = ['eastmoney', 'eastmoney_multi']  # 东方财富(单板块+多板块)
    
    # 如果用户没有指定sources，使用默认源
    # 如果用户指定了sources，则使用用户选择的源（但过滤掉无效的源）
    if not sources:
        sources = stable_sources
    else:
        # 用户指定了源，过滤只保留有效的源
        valid_sources = [s for s in sources if s in NEWS_SOURCES]
        
        # 检查这些源是否能获取到有效数据（有正文内容的）
        if valid_sources:
            test_sources = []
            for src in valid_sources:
                if src in NEWS_SOURCES:
                    try:
                        test_news = NEWS_SOURCES[src].fetch(limit=3)
                        # 检查是否有数据且有正文内容
                        has_content = any(n.get('content') for n in test_news)
                        if test_news and has_content:
                            test_sources.append(src)
                    except:
                        pass
            
            if test_sources:
                sources = test_sources
            else:
                # 用户选择的源没有有效数据，返回空结果
                return {
                    "success": True,
                    "data": {
                        "total": 0,
                        "list": [],
                        "sources": valid_sources
                    }
                }
        else:
            # 用户指定的源全部无效，使用默认源
            sources = stable_sources
    
    # 检查缓存
    cache_key_params = {
        'sources': ','.join(sorted(sources)),
        'limit': limit,
        'keyword': keyword,
        'category': category,
    }
    
    cached = _news_cache.get('all', **cache_key_params)
    if cached:
        return cached
    
    all_news = []
    
    def fetch_single_source(source_name):
        """单线程获取单个新闻源"""
        if source_name not in NEWS_SOURCES:
            return []
        source = NEWS_SOURCES[source_name]
        try:
            # 传递时间筛选参数
            news_list = source.fetch(limit=limit, keyword=keyword, start_date=start_date, end_date=end_date)
            if news_list:
                logger.info(f"从 {source_name} 获取 {len(news_list)} 条新闻")
                return news_list
        except Exception as e:
            logger.warning(f"从 {source_name} 获取新闻失败: {e}")
        return []
    
    # 并发获取（最多3个源）
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(fetch_single_source, src) for src in sources]
            
            # 等待所有任务完成，最多5秒
            for future in futures:
                try:
                    news = future.result(timeout=5)
                    if news:
                        all_news.extend(news)
                except Exception as e:
                    pass
    except Exception as e:
        logger.warning(f"并发获取新闻异常: {e}")
    
    # 按时间排序
    all_news.sort(key=lambda x: x.get('datetime', ''), reverse=True)
    
    # 分类过滤 - 支持精确匹配和金融类过滤
    # 默认过滤掉综合类新闻，只保留财经相关
    if category:
        if category.lower() in ['财经', '金融', 'financial', 'all']:
            # 保留所有分类
            pass
        elif category.lower() in ['综合', '全部']:
            # 显式要求综合类
            pass
        else:
            all_news = [n for n in all_news if n.get('category', '') == category]
    else:
        # 不过滤，显示所有分类
        pass
    
    # 时间筛选过滤
    if start_date or end_date:
        filtered_news = []
        for news in all_news:
            news_time = news.get('datetime', '')
            if not news_time:
                continue
            try:
                # 解析新闻时间
                news_dt = datetime.strptime(news_time, '%Y-%m-%d %H:%M')
                
                # 检查是否在时间范围内
                if start_date:
                    start_dt = datetime.strptime(start_date, '%Y%m%d')
                    if news_dt < start_dt:
                        continue
                if end_date:
                    end_dt = datetime.strptime(end_date, '%Y%m%d')
                    # 结束日期包含当天，所以设置为第二天零点
                    end_dt = end_dt + timedelta(days=1)
                    if news_dt >= end_dt:
                        continue
                        
                filtered_news.append(news)
            except Exception as e:
                # 如果解析失败，保留这条新闻
                filtered_news.append(news)
        all_news = filtered_news
    
    # 去重
    seen = set()
    unique_news = []
    for news in all_news:
        if news['title'] not in seen:
            seen.add(news['title'])
            # 清洗content中的HTML标签
            if news.get('content'):
                news['content'] = clean_html_content(news['content'])
            unique_news.append(news)
    
    result = {
        "success": True,
        "data": {
            "total": len(unique_news[:limit]),
            "list": unique_news[:limit],
            "sources": sources
        }
    }
    
    _news_cache.set('all', result, **cache_key_params)
    
    return result


def get_news_sources() -> List[Dict]:
    """获取新闻源列表"""
    return [
        {"name": "eastmoney", "display_name": "东方财富", "enabled": True},
        {"name": "sohu", "display_name": "搜狐", "enabled": True},
        {"name": "pengpai", "display_name": "澎湃新闻", "enabled": True},
        {"name": "cls", "display_name": "财联社", "enabled": False},
        {"name": "sina", "display_name": "新浪财经", "enabled": False},
        {"name": "qq", "display_name": "腾讯财经", "enabled": False},
        {"name": "hexun", "display_name": "和讯网", "enabled": False},
        {"name": "ifeng", "display_name": "凤凰网", "enabled": False},
        {"name": "stcn", "display_name": "证券时报", "enabled": False},
        {"name": "yicai", "display_name": "第一财经", "enabled": False},
        {"name": "wallstreet", "display_name": "华尔街见闻", "enabled": False},
        {"name": "iwencai", "display_name": "同花顺", "enabled": False},
        {"name": "xueqiu", "display_name": "雪球", "enabled": False},
        {"name": "weibo", "display_name": "微博财经", "enabled": False},
    ]


def clear_news_cache():
    """清空缓存"""
    _news_cache.clear()
    return {"success": True, "message": "缓存已清空"}
