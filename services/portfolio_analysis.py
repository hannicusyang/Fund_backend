# services/portfolio_analysis.py
# 组合智能分析服务

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


class PortfolioAnalysisService:
    """组合智能分析服务"""
    
    def __init__(self):
        self.api_key = MINIMAX_API_KEY
        self.base_url = 'https://api.minimax.com/anthropic'
        self.enabled = bool(self.api_key and len(self.api_key) > 10)
        if self.enabled:
            logger.info(f"组合AI分析服务已启用，API: {self.base_url}")
    
    def analyze_portfolio(self, holdings: List[Dict], weights: List[float]) -> Dict:
        """
        分析投资组合
        
        holdings: 持仓列表 [{stock_code, stock_name, weight, ...}]
        weights: 权重列表
        """
        # 计算组合指标
        portfolio_metrics = self._calculate_portfolio_metrics(holdings, weights)
        
        if not self.enabled:
            return self._local_portfolio_analysis(portfolio_metrics)
        
        try:
            prompt = self._build_portfolio_prompt(portfolio_metrics)
            result = self._call_ai(prompt)
            if result:
                return self._parse_result(result, portfolio_metrics)
        except Exception as e:
            logger.error(f"组合AI分析失败: {e}")
        
        return self._local_portfolio_analysis(portfolio_metrics)
    
    def generate_rebalance_advice(self, holdings: List[Dict], weights: List[float], 
                                   target_weights: List[float] = None) -> Dict:
        """生成调仓建议"""
        current_metrics = self._calculate_portfolio_metrics(holdings, weights)
        
        if target_weights:
            # 计算需要调整的仓位
            adjustments = []
            for i, (h, w, tw) in enumerate(zip(holdings, weights, target_weights)):
                diff = tw - w
                if abs(diff) > 1:  # 差异超过1%
                    adjustments.append({
                        "stock": h.get('stock_name', h.get('fund_name', '')),
                        "current": f"{w:.1f}%",
                        "target": f"{tw:.1f}%",
                        "action": "增持" if diff > 0 else "减持",
                        "change": f"{diff:+.1f}%"
                    })
            
            return {
                "adjustments": adjustments,
                "rebalance_needed": len(adjustments) > 0,
                "total_change": sum(abs(a['change']) for a in adjustments) / 2
            }
        
        # AI生成建议
        if not self.enabled:
            return self._local_rebalance_advice(current_metrics)
        
        try:
            prompt = self._build_rebalance_prompt(current_metrics)
            result = self._call_ai(prompt)
            if result:
                return self._parse_rebalance(result, current_metrics)
        except Exception as e:
            logger.error(f"调仓建议生成失败: {e}")
        
        return self._local_rebalance_advice(current_metrics)
    
    def _calculate_portfolio_metrics(self, holdings: List[Dict], weights: List[float]) -> Dict:
        """计算组合指标"""
        if not holdings:
            return {}
        
        # 行业分布
        sector_weights = {}
        for h, w in zip(holdings, weights):
            sector = h.get('sector', '其他')
            sector_weights[sector] = sector_weights.get(sector, 0) + w
        
        # 排序行业
        sorted_sectors = sorted(sector_weights.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "holdings_count": len(holdings),
            "total_value": sum(h.get('value', 0) for h in holdings),
            "sector_distribution": dict(sorted_sectors[:5]),
            "top_sector": sorted_sectors[0] if sorted_sectors else None,
            "sector_concentration": sorted_sectors[0][1] if sorted_sectors else 0,
            "diversification_score": self._calc_diversification(sorted_sectors),
            "holdings": [
                {
                    "name": h.get('stock_name', h.get('fund_name', '')),
                    "code": h.get('stock_code', h.get('fund_code', '')),
                    "weight": w,
                    "sector": h.get('sector', '其他')
                }
                for h, w in zip(holdings, weights)
            ]
        }
    
    def _calc_diversification(self, sectors: List[tuple]) -> str:
        """计算分散度"""
        if not sectors:
            return "低"
        
        top_concentration = sectors[0][1]
        if top_concentration > 40:
            return "低"
        elif top_concentration > 25:
            return "一般"
        else:
            return "高"
    
    def _build_portfolio_prompt(self, metrics: Dict) -> str:
        """构建组合分析提示词"""
        holdings_str = "\n".join([
            f"- {h['name']}({h['code']}): {h['weight']}%, {h['sector']}"
            for h in metrics.get('holdings', [])[:10]
        ])
        
        sectors_str = "\n".join([
            f"- {s}: {w:.1f}%" 
            for s, w in metrics.get('sector_distribution', {}).items()
        ])
        
        return f"""作为资深投资顾问，请分析以下投资组合。

【组合概览】
- 持仓数量: {metrics.get('holdings_count', 0)}只
- 总市值: {metrics.get('total_value', 0):.2f}万

【持仓明细】
{holdings_str}

【行业分布】
{sectors_str}

【行业集中度】
- 第一大行业: {metrics.get('top_sector', ('N/A', 0))}
- 集中度: {metrics.get('sector_concentration', 0):.1f}%
- 分散度: {metrics.get('diversification_score', 'N/A')}

请返回JSON格式的分析报告:
{{
    "综合评分": "75/100",
    "收益评分": 70,
    "风险评分": 75,
    "分散度评分": 80,
    "优势": ["优势1", "优势2"],
    "风险点": ["风险1"],
    "行业风险": "行业集中度评估",
    "调仓建议": "简要建议",
    "风险提示": "提示内容"
}}

只返回JSON，不要其他内容。"""
    
    def _build_rebalance_prompt(self, metrics: Dict) -> str:
        """构建调仓建议提示词"""
        return f"""作为资深投资顾问，请为以下组合生成调仓建议。

【当前组合】
- 持仓数量: {metrics.get('holdings_count', 0)}只
- 行业集中度: {metrics.get('sector_concentration', 0):.1f}%
- 分散度: {metrics.get('diversification_score', 'N/A')}

【行业分布】
{json.dumps(metrics.get('sector_distribution', {}), ensure_ascii=False)}

请返回JSON格式的调仓建议:
{{
    "建议增持": ["股票A", "股票B"],
    "建议减持": ["股票C"],
    "增持理由": "简单说明",
    "减持理由": "简单说明",
    "维持不变": ["股票D"],
    "整体建议": "总体建议"
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
    
    def _parse_result(self, ai_text: str, metrics: Dict) -> Dict:
        """解析AI返回结果"""
        try:
            json_match = re.search(r'\{[^{}]*\}', ai_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result['_ai_analysis'] = True
                result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
                result['portfolio_metrics'] = metrics
                return result
        except Exception as e:
            logger.error(f"解析AI结果失败: {e}")
        
        return self._local_portfolio_analysis(metrics)
    
    def _parse_rebalance(self, ai_text: str, metrics: Dict) -> Dict:
        """解析调仓建议"""
        try:
            json_match = re.search(r'\{[^{}]*\}', ai_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result['_ai_analysis'] = True
                result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
                return result
        except Exception as e:
            logger.error(f"解析调仓建议失败: {e}")
        
        return self._local_rebalance_advice(metrics)
    
    def _local_portfolio_analysis(self, metrics: Dict) -> Dict:
        """本地组合分析"""
        score = 70
        if metrics.get('sector_concentration', 100) < 30:
            score += 10
        
        return {
            "综合评分": f"{min(score, 100)}/100",
            "收益评分": score - 5,
            "风险评分": score,
            "分散度评分": score + 5,
            "优势": ["行业分散"],
            "风险点": ["市场风险"],
            "调仓建议": "建议保持当前配置",
            "analysis_method": "local"
        }
    
    def _local_rebalance_advice(self, metrics: Dict) -> Dict:
        """本地调仓建议"""
        return {
            "建议增持": [],
            "建议减持": [],
            "整体建议": "当前组合配置合理",
            "analysis_method": "local"
        }


# 单例
_portfolio_analysis_service = PortfolioAnalysisService()


def get_portfolio_analysis_service() -> PortfolioAnalysisService:
    return _portfolio_analysis_service


def analyze_portfolio_with_ai(holdings: List[Dict], weights: List[float]) -> Dict:
    return _portfolio_analysis_service.analyze_portfolio(holdings, weights)


def generate_rebalance_advice(holdings: List[Dict], weights: List[float], 
                               target_weights: List[float] = None) -> Dict:
    return _portfolio_analysis_service.generate_rebalance_advice(holdings, weights, target_weights)
