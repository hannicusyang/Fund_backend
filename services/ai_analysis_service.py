# services/ai_analysis_service.py
# AI分析服务 - 使用MiniMax API进行智能分析

import requests
import json
import re
from typing import Dict, List, Optional
from config.logging_config import logger
from config.env_config import MINIMAX_API_KEY, MINIMAX_BASE_URL


class AIService:
    """AI分析服务 - 支持MiniMax API"""
    
    def __init__(self):
        self.api_key = MINIMAX_API_KEY
        self.base_url = MINIMAX_BASE_URL
        self.enabled = bool(self.api_key and len(self.api_key) > 10)
        if not self.enabled:
            logger.info("MiniMax API未配置或Key无效，将使用本地分析")
    
    def analyze_news(self, news_list: List[Dict]) -> Dict:
        """使用MiniMax API分析新闻数据"""
        if not self.enabled:
            logger.info("使用本地分析（未配置MiniMax API）")
            return None
        
        try:
            news_text = self._build_news_summary(news_list)
            prompt = self._build_analysis_prompt(news_text)
            result = self._call_minimax(prompt)
            
            if result:
                return self._parse_ai_result(result, news_list)
            
        except Exception as e:
            logger.error(f"MiniMax API调用失败: {e}")
        
        return None
    
    def _build_news_summary(self, news_list: List[Dict], max_count: int = 30) -> str:
        """构建新闻摘要文本"""
        summaries = []
        for i, news in enumerate(news_list[:max_count], 1):
            title = news.get('title', '')
            source = news.get('source', '')
            summaries.append(f"{i}. [{source}] {title}")
        return "\n".join(summaries)
    
    def _build_analysis_prompt(self, news_text: str) -> str:
        """构建专业严谨的分析提示词"""
        return f"""作为资深金融分析师（CFA），请以专业严谨的态度分析以下财经新闻。

【新闻】
{news_text}

【返回格式】（严格JSON）
{{
    "sentiment": "情绪（乐观/中性/悲观）",
    "sentiment_score": 75,
    "sentiment_emoji": "😊",
    "sentiment_detail": {{
        "positive_signals": ["积极信号1", "积极信号2"],
        "negative_signals": ["负面信号1"],
        "confidence": "高/中/低"
    }},
    "hot_topics": ["热点1","热点2","热点3","热点4","热点5"],
    "hot_topics_detail": [{{"topic":"话题","heat":90,"duration":"短期/中期/长期"}}],
    "opportunity_sectors": [{{"sector":"板块","logic":"看好逻辑","leaders":["龙头"],"potential":"涨幅"}}],
    "risks": [{{"risk":"风险","level":"高/中/低"}}],
    "suggestion": "投资建议",
    "仓位建议": "保守/中性/激进",
    "操作建议": "买入/持有/卖出/观望",
    "summary": "总结（80字以内）",
    "disclaimer": "本报告仅供参考，不构成投资建议"
}}

直接返回JSON，不要其他内容。"""
    
    def _call_minimax(self, prompt: str) -> Optional[str]:
        """调用MiniMax API"""
        try:
            import anthropic
            
            client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            message = client.messages.create(
                model="MiniMax-M2.5",
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            for block in message.content:
                if hasattr(block, 'text'):
                    return block.text
                elif isinstance(block, dict) and block.get('type') == 'text':
                    return block.get('text', '')
            
            return None
            
        except ImportError:
            logger.error("请安装anthropic库: pip install anthropic")
            return None
        except Exception as e:
            logger.error(f"MiniMax API调用异常: {e}")
            return None
    
    def _parse_ai_result(self, ai_text: str, news_list: List[Dict]) -> Dict:
        """解析AI返回的结果"""
        try:
            ai_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', ai_text)
            
            # Try direct JSON parse
            try:
                result = json.loads(ai_text)
                if isinstance(result, dict):
                    result['_ai_analysis'] = True
                    result['news_count'] = len(news_list)
                    result['sources'] = list(set([n.get('source', '未知') for n in news_list]))
                    self._add_sentiment_detail(result)
                    return result
            except:
                pass
            
            # Try extracting JSON block
            json_match = re.search(r'\{[^{}]*\}', ai_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result['_ai_analysis'] = True
                result['news_count'] = len(news_list)
                result['sources'] = list(set([n.get('source', '未知') for n in news_list]))
                self._add_sentiment_detail(result)
                return result
            
        except Exception as e:
            logger.error(f"解析AI结果失败: {e}")
        
        return None
    
    def _add_sentiment_detail(self, result: Dict):
        """添加情感详情"""
        sentiment = result.get('sentiment', '中性')
        if '暖' in sentiment or '乐' in sentiment:
            result['sentiment_detail'] = {'positive_ratio': 70, 'negative_ratio': 30}
        elif '谨' in sentiment or '悲' in sentiment or '冷' in sentiment:
            result['sentiment_detail'] = {'positive_ratio': 30, 'negative_ratio': 70}
        else:
            result['sentiment_detail'] = {'positive_ratio': 50, 'negative_ratio': 50}


_ai_service = AIService()


def get_ai_service() -> AIService:
    return _ai_service


def analyze_news_with_ai(news_list: List[Dict]) -> Optional[Dict]:
    return _ai_service.analyze_news(news_list)
