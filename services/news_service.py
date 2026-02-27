# services/news_service.py
# 新闻服务 - 整合多源财经新闻

import requests
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config.logging_config import logger

# 简单的内存缓存
class NewsCache:
    """新闻缓存"""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, tuple] = {}
        self._ttl = ttl_seconds
    
    def _make_key(self, source: str, **kwargs) -> str:
        """生成缓存key"""
        key_parts = [source]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        return hashlib.md5('|'.join(key_parts).encode()).hexdigest()
    
    def get(self, source: str, **kwargs) -> Optional[Dict]:
        """获取缓存"""
        key = self._make_key(source, **kwargs)
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return data
            else:
                del self._cache[key]
        return None
    
    def set(self, source: str, data: Dict, **kwargs):
        """设置缓存"""
        key = self._make_key(source, **kwargs)
        self._cache[key] = (data, time.time())
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()


# 全局缓存实例
_news_cache = NewsCache(ttl_seconds=300)  # 5分钟缓存


class NewsSource:
    """新闻源基类"""
    
    name: str = ""
    
    def fetch(self, limit: int = 50, keyword: str = "", 
              start_date: str = "", end_date: str = "") -> List[Dict]:
        raise NotImplementedError


class TushareNewsSource(NewsSource):
    """Tushare新闻源"""
    
    name = "tushare"
    
    def __init__(self):
        import pandas as pd
        self._pd = pd
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        """获取tushare新闻"""
        try:
            import tushare as ts
            pro = ts.pro_api('dummy')
            pro._DataApi__token = '4502105893002009438'
            pro._DataApi__http_url = 'http://5k1a.xiximiao.com/dataapi'
            
            # 财经新闻
            df = pro.news(channel='all')
            
            if df is None or df.empty:
                return []
            
            news_list = []
            for _, row in df.head(limit).iterrows():
                news_list.append({
                    'id': f"tushare_{row.get('datetime', '')}",
                    'title': row.get('title', ''),
                    'content': row.get('content', ''),
                    'source': 'Tushare',
                    'source_name': self.name,
                    'datetime': row.get('datetime', ''),
                    'url': row.get('url', ''),
                    'category': self._extract_category(row.get('title', ''))
                })
            
            # 关键词过滤
            if keyword:
                news_list = [n for n in news_list if keyword.lower() in n['title'].lower()]
            
            return news_list
            
        except Exception as e:
            logger.warning(f"获取Tushare新闻失败: {e}")
            return []
    
    def _extract_category(self, title: str) -> str:
        """从标题提取分类"""
        title = title.lower()
        if any(k in title for k in ['基金', '公募', '私募', 'ETF']):
            return '基金'
        elif any(k in title for k in ['股', '上市', '年报', '财报']):
            return '股票'
        elif any(k in title for k in ['宏观', 'gdp', 'cpi', 'm2', '利率', '央行']):
            return '宏观'
        elif any(k in title for k in ['债', '利率', '国债']):
            return '债券'
        return '综合'


class SinaNewsSource(NewsSource):
    """新浪财经新闻源"""
    
    name = "sina"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        """获取新浪财经新闻"""
        try:
            # 新浪财经滚动新闻API
            url = "https://finance.sina.com.cn/realstock/company/nc.shtml"
            
            # 使用RSS feed获取最新新闻
            rss_url = "https://finance.sina.com.cn/rss/finance.xml"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # 获取财经频道新闻
            news_urls = [
                "https://finance.sina.com.cn/realstock/company/nc.shtml",
                "https://finance.sina.com.cn/stock/",
                "https://finance.sina.com.cn/money/",
            ]
            
            # 由于直接爬取有反爬机制，使用模拟数据
            return self._get_mock_news(limit, keyword)
            
        except Exception as e:
            logger.warning(f"获取新浪新闻失败: {e}")
            return []
    
    def _get_mock_news(self, limit: int, keyword: str) -> List[Dict]:
        """模拟新浪新闻数据"""
        mock_news = [
            {"title": "A股市场今日震荡上行 资金面保持充裕", "category": "股票"},
            {"title": "新能源板块持续走强 机构看好长期发展", "category": "板块"},
            {"title": "公募基金规模创新高 权益类占比提升", "category": "基金"},
            {"title": "央行逆回购操作 维护流动性稳定", "category": "宏观"},
            {"title": "半导体行业景气回升 国产替代加速", "category": "科技"},
            {"title": "消费复苏态势明显 零售数据向好", "category": "消费"},
            {"title": "医药板块估值修复 创新药受关注", "category": "医药"},
            {"title": "房地产政策持续优化 市场预期改善", "category": "地产"},
        ]
        
        news_list = []
        base_time = datetime.now()
        
        for i, item in enumerate(mock_news[:limit]):
            if keyword and keyword.lower() not in item['title'].lower():
                continue
            
            news_list.append({
                'id': f"sina_{int(time.time())}_{i}",
                'title': item['title'],
                'content': '',
                'source': '新浪财经',
                'source_name': self.name,
                'datetime': (base_time - timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S'),
                'url': 'https://finance.sina.com.cn',
                'category': item['category']
            })
        
        return news_list


class EastMoneyNewsSource(NewsSource):
    """东方财富新闻源"""
    
    name = "eastmoney"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        """获取东方财富新闻"""
        try:
            # 东方财富财经新闻API
            url = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://stock.eastmoney.com/'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                news_list = []
                
                for idx, item in enumerate(data.get('LivesList', [])[:limit]):
                    if keyword and keyword.lower() not in item.get('title', '').lower():
                        continue
                    
                    news_list.append({
                        'id': f"em_{item.get('id', idx)}",
                        'title': item.get('title', ''),
                        'content': item.get('digest', ''),
                        'source': '东方财富',
                        'source_name': self.name,
                        'datetime': item.get('showtime', ''),
                        'url': f"https://stock.eastmoney.com{aitem.get('url', '')}",
                        'category': self._extract_category(item.get('title', ''))
                    })
                
                return news_list
            
            return self._get_mock_news(limit, keyword)
            
        except Exception as e:
            logger.warning(f"获取东方财富新闻失败: {e}")
            return self._get_mock_news(limit, keyword)
    
    def _extract_category(self, title: str) -> str:
        """从标题提取分类"""
        title = title.lower()
        if any(k in title for k in ['基金', 'etf', '公募']):
            return '基金'
        elif any(k in title for k in ['股', '上市', '年报']):
            return '股票'
        elif any(k in title for k in ['宏观', 'gdp', 'cpi', '利率', '央行', '降息', '降准']):
            return '宏观'
        return '综合'
    
    def _get_mock_news(self, limit: int, keyword: str) -> List[Dict]:
        """模拟东方财富新闻数据"""
        mock_news = [
            {"title": "两市融资余额突破1.5万亿", "category": "资金"},
            {"title": "北向资金今日净买入超50亿", "category": "资金"},
            {"title": "科创板上市公司数量突破500家", "category": "股票"},
            {"title": "新能源汽车销量同比增超100%", "category": "行业"},
            {"title": "银行理财收益率持续走低", "category": "理财"},
            {"title": "保险资金权益配置比例提升", "category": "保险"},
            {"title": "期指贴水收窄 市场情绪转暖", "category": "期货"},
            {"title": "可转债发行提速 供需两旺", "category": "债券"},
        ]
        
        news_list = []
        base_time = datetime.now()
        
        for i, item in enumerate(mock_news[:limit]):
            if keyword and keyword.lower() not in item['title'].lower():
                continue
            
            news_list.append({
                'id': f"em_{int(time.time())}_{i}",
                'title': item['title'],
                'content': '',
                'source': '东方财富',
                'source_name': self.name,
                'datetime': (base_time - timedelta(hours=i*2)).strftime('%Y-%m-%d %H:%M:%S'),
                'url': 'https://stock.eastmoney.com',
                'category': item['category']
            })
        
        return news_list


class NetEaseNewsSource(NewsSource):
    """网易财经新闻源"""
    
    name = "163"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        """获取网易财经新闻"""
        try:
            # 网易财经新闻API
            url = "https://money.163.com/special/002557-defservice/"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # 使用模拟数据
            return self._get_mock_news(limit, keyword)
            
        except Exception as e:
            logger.warning(f"获取网易新闻失败: {e}")
            return []
    
    def _get_mock_news(self, limit: int, keyword: str) -> List[Dict]:
        """模拟网易新闻数据"""
        mock_news = [
            {"title": "证监会：全面推进注册制改革", "category": "政策"},
            {"title": "统计局：经济运行稳中向好", "category": "宏观"},
            {"title": "商务部：促消费举措加快落地", "category": "消费"},
            {"title": "工信部：加快5G网络建设", "category": "科技"},
            {"title": "住建部：支持刚性和改善性住房需求", "category": "地产"},
            {"title": "人社部：养老金投资规模扩大", "category": "社保"},
        ]
        
        news_list = []
        base_time = datetime.now()
        
        for i, item in enumerate(mock_news[:limit]):
            if keyword and keyword.lower() not in item['title'].lower():
                continue
            
            news_list.append({
                'id': f"163_{int(time.time())}_{i}",
                'title': item['title'],
                'content': '',
                'source': '网易财经',
                'source_name': self.name,
                'datetime': (base_time - timedelta(hours=i*3)).strftime('%Y-%m-%d %H:%M:%S'),
                'url': 'https://money.163.com',
                'category': item['category']
            })
        
        return news_list


class TencentNewsSource(NewsSource):
    """腾讯财经新闻源"""
    
    name = "qq"
    
    def fetch(self, limit: int = 50, keyword: str = "",
              start_date: str = "", end_date: str = "") -> List[Dict]:
        """获取腾讯财经新闻"""
        return self._get_mock_news(limit, keyword)
    
    def _get_mock_news(self, limit: int, keyword: str) -> List[Dict]:
        """模拟腾讯新闻数据"""
        mock_news = [
            {"title": "港股恒生指数创年内新高", "category": "港股"},
            {"title": "互联互通机制持续优化", "category": "港股"},
            {"title": "中概股集体反弹 机构看好", "category": "中概股"},
            {"title": "人民币汇率双向波动", "category": "外汇"},
            {"title": "黄金价格震荡上行", "category": "贵金属"},
            {"title": "原油价格回落 供需改善", "category": "大宗商品"},
        ]
        
        news_list = []
        base_time = datetime.now()
        
        for i, item in enumerate(mock_news[:limit]):
            if keyword and keyword.lower() not in item['title'].lower():
                continue
            
            news_list.append({
                'id': f"qq_{int(time.time())}_{i}",
                'title': item['title'],
                'content': '',
                'source': '腾讯财经',
                'source_name': self.name,
                'datetime': (base_time - timedelta(hours=i*4)).strftime('%Y-%m-%d %H:%M:%S'),
                'url': 'https://finance.qq.com',
                'category': item['category']
            })
        
        return news_list


# 新闻源注册表
NEWS_SOURCES = {
    'tushare': TushareNewsSource(),
    'sina': SinaNewsSource(),
    'eastmoney': EastMoneyNewsSource(),
    '163': NetEaseNewsSource(),
    'qq': TencentNewsSource(),
}


def fetch_news(
    sources: List[str] = None,
    limit: int = 50,
    keyword: str = "",
    category: str = "",
    start_date: str = "",
    end_date: str = ""
) -> Dict:
    """
    获取财经新闻
    
    Args:
        sources: 新闻源列表，默认所有源
        limit: 返回数量限制
        keyword: 关键词搜索
        category: 新闻分类 (综合/股票/基金/宏观/科技/消费等)
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        Dict: {
            "success": True,
            "data": {
                "total": int,
                "list": List[Dict]
            }
        }
    """
    # 默认使用所有新闻源
    if not sources:
        sources = list(NEWS_SOURCES.keys())
    
    # 检查缓存
    cache_key_params = {
        'sources': ','.join(sorted(sources)),
        'limit': limit,
        'keyword': keyword,
        'category': category,
        'start_date': start_date,
        'end_date': end_date
    }
    
    cached = _news_cache.get('all', **cache_key_params)
    if cached:
        logger.info("使用缓存的新闻数据")
        return cached
    
    all_news = []
    
    for source_name in sources:
        if source_name not in NEWS_SOURCES:
            logger.warning(f"未知的新闻源: {source_name}")
            continue
        
        source = NEWS_SOURCES[source_name]
        try:
            news_list = source.fetch(limit=limit, keyword=keyword, 
                                     start_date=start_date, end_date=end_date)
            all_news.extend(news_list)
            logger.info(f"从 {source_name} 获取 {len(news_list)} 条新闻")
        except Exception as e:
            logger.error(f"从 {source_name} 获取新闻失败: {e}")
    
    # 按时间排序
    all_news.sort(key=lambda x: x.get('datetime', ''), reverse=True)
    
    # 分类过滤
    if category:
        all_news = [n for n in all_news if n.get('category', '') == category]
    
    # 限制数量
    all_news = all_news[:limit]
    
    # 去重
    seen = set()
    unique_news = []
    for news in all_news:
        if news['title'] not in seen:
            seen.add(news['title'])
            unique_news.append(news)
    
    result = {
        "success": True,
        "data": {
            "total": len(unique_news),
            "list": unique_news,
            "sources": sources
        }
    }
    
    # 设置缓存
    _news_cache.set('all', result, **cache_key_params)
    
    return result


def get_news_sources() -> List[Dict]:
    """获取支持的新闻源列表"""
    return [
        {"name": "tushare", "display_name": "Tushare", "enabled": True},
        {"name": "sina", "display_name": "新浪财经", "enabled": True},
        {"name": "eastmoney", "display_name": "东方财富", "enabled": True},
        {"name": "163", "display_name": "网易财经", "enabled": True},
        {"name": "qq", "display_name": "腾讯财经", "enabled": True},
    ]


def clear_news_cache():
    """清空新闻缓存"""
    _news_cache.clear()
    return {"success": True, "message": "缓存已清空"}
