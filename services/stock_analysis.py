# services/stock_analysis.py
# 股票智能分析服务

import os

# 先设置环境变量（必须在import anthropic之前）
os.environ['ANTHROPIC_BASE_URL'] = 'https://api.minimax.com/anthropic'
from config.env_config import MINIMAX_API_KEY
os.environ['ANTHROPIC_API_KEY'] = MINIMAX_API_KEY

import json
import re
from typing import Dict, List, Optional
from datetime import datetime
from config.logging_config import logger


class StockAnalysisService:
    """股票智能分析服务"""
    
    def __init__(self):
        self.api_key = MINIMAX_API_KEY
        self.base_url = 'https://api.minimax.com/anthropic'
        self.enabled = bool(self.api_key and len(self.api_key) > 10)
        if self.enabled:
            logger.info(f"股票AI分析服务已启用，API: {self.base_url}")
    
    def analyze_stock(self, stock_data: Dict) -> Dict:
        """
        分析单只股票
        
        stock_data 包含:
        - stock_code: 股票代码
        - stock_name: 股票名称
        - price: 当前价格
        - pe: 市盈率
        - pb: 市净率
        - market_cap: 市值
        - revenue_growth: 营收增速
        - profit_growth: 利润增速
        - kline_data: K线数据(用于技术分析)
        - technical_signals: 技术信号
        """
        if not self.enabled:
            return self._local_analysis(stock_data)
        
        try:
            prompt = self._build_stock_prompt(stock_data)
            result = self._call_ai(prompt)
            if result:
                return self._parse_result(result, stock_data)
        except Exception as e:
            logger.error(f"股票AI分析失败: {e}")
        
        return self._local_analysis(stock_data)
    
    def analyze_technical(self, stock_data: Dict) -> Dict:
        """技术分析"""
        kline = stock_data.get('kline_data', {})
        signals = stock_data.get('technical_signals', {})
        
        trend = "震荡"
        if signals.get('ma_trend') == 'bullish':
            trend = "上升"
        elif signals.get('ma_trend') == 'bearish':
            trend = "下降"
        
        return {
            "当前趋势": trend,
            "均线形态": signals.get('ma_signal', '缠绕'),
            "MACD": signals.get('macd_signal', '中性'),
            "RSI": signals.get('rsi', 50),
            "支撑位": stock_data.get('support', 'N/A'),
            "阻力位": stock_data.get('resistance', 'N/A'),
            "成交量": kline.get('volume', 'N/A'),
            "技术信号": "买入" if signals.get('macd_signal') == '金叉' else "观望"
        }
    
    def _build_stock_prompt(self, stock: Dict) -> str:
        """构建股票分析提示词"""
        basic = stock.get('basic', {})
        tech = self.analyze_technical(stock)
        
        return f"""作为资深金融分析师（CFA），请分析以下股票。

【基本信息】
- 股票代码: {stock.get('stock_code', '')}
- 股票名称: {stock.get('stock_name', '')}
- 当前价格: {stock.get('price', 'N/A')}元
- 市值: {basic.get('market_cap', 'N/A')}亿
- PE: {basic.get('pe', 'N/A')}
- PB: {basic.get('pb', 'N/A')}
- 营收增速: {basic.get('revenue_growth', 'N/A')}%
- 净利润增速: {basic.get('profit_growth', 'N/A')}%

【技术面】
- 当前趋势: {tech.get('当前趋势', 'N/A')}
- 均线形态: {tech.get('均线形态', 'N/A')}
- MACD: {tech.get('MACD', 'N/A')}
- RSI: {tech.get('RSI', 'N/A')}
- 支撑位: {tech.get('支撑位', 'N/A')}元
- 阻力位: {tech.get('阻力位', 'N/A')}元

请返回JSON格式的分析报告:
{{
    "综合评分": "78/100",
    "基本面评分": 80,
    "技术面评分": 75,
    "估值评分": 70,
    "买入理由": ["理由1", "理由2"],
    "风险提示": ["风险1"],
    "操作建议": "建议买入/建议持有/建议卖出",
    "目标价位": "XX元",
    "止损价位": "XX元",
    "持有期限": "短期/中期/长期"
}}

只返回JSON，不要其他内容。"""
    
    def _call_ai(self, prompt: str) -> Optional[str]:
        """调用AI API"""
        try:
            import anthropic
            
            client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0  # 30秒超时
            )
            
            message = client.messages.create(
                model="MiniMax-M2.5",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result_text = ""
            for block in message.content:
                if hasattr(block, 'text'):
                    result_text += block.text
                elif hasattr(block, 'thinking'):
                    pass
                elif isinstance(block, dict):
                    if block.get('type') == 'text':
                        result_text += block.get('text', '')
            
            return result_text if result_text else None
            
        except Exception as e:
            logger.error(f"MiniMax API调用失败: {e}")
            return None
    
    def _parse_result(self, ai_text: str, stock_data: Dict) -> Dict:
        """解析AI返回结果"""
        try:
            json_match = re.search(r'\{[^{}]*\}', ai_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result['_ai_analysis'] = True
                result['stock_code'] = stock_data.get('stock_code')
                result['stock_name'] = stock_data.get('stock_name')
                result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
                # 添加技术分析
                result['技术面'] = self.analyze_technical(stock_data)
                return result
        except Exception as e:
            logger.error(f"解析AI结果失败: {e}")
        
        return self._local_analysis(stock_data)
    
    def _local_analysis(self, stock: Dict) -> Dict:
        """本地分析（无API时）"""
        basic = stock.get('basic', {})
        score = 60
        
        # 简单评分
        pe = basic.get('pe', 0)
        if 0 < pe < 30:
            score += 10
        if basic.get('profit_growth', 0) > 10:
            score += 10
        
        tech = self.analyze_technical(stock)
        
        return {
            "综合评分": f"{min(score, 100)}/100",
            "基本面评分": score,
            "技术面评分": score - 5,
            "买入理由": ["估值合理"],
            "风险提示": ["市场风险"],
            "操作建议": "建议持有",
            "analysis_method": "local",
            "技术面": tech
        }


# 单例
_stock_analysis_service = StockAnalysisService()


def get_stock_analysis_service() -> StockAnalysisService:
    return _stock_analysis_service


def analyze_stock_with_ai(stock_data: Dict) -> Dict:
    return _stock_analysis_service.analyze_stock(stock_data)
