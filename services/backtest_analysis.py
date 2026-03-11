# services/backtest_analysis.py
# 回测智能分析服务

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


class BacktestAnalysisService:
    """回测智能分析服务"""
    
    def __init__(self):
        self.api_key = MINIMAX_API_KEY
        self.base_url = 'https://api.minimax.com/anthropic'
        self.enabled = bool(self.api_key and len(self.api_key) > 10)
        if self.enabled:
            logger.info(f"回测AI分析服务已启用，API: {self.base_url}")
    
    def analyze_backtest(self, backtest_result: Dict) -> Dict:
        """
        分析回测结果
        
        backtest_result 包含:
        - total_return: 总收益率
        - annual_return: 年化收益
        - benchmark_return: 基准收益
        - excess_return: 超额收益
        - max_drawdown: 最大回撤
        - sharpe: 夏普比率
        - calmar: 卡玛比率
        - volatility: 波动率
        - win_rate: 胜率
        - trade_count: 交易次数
        - trades: 交易记录列表
        """
        if not self.enabled:
            return self._local_backtest_analysis(backtest_result)
        
        try:
            prompt = self._build_backtest_prompt(backtest_result)
            result = self._call_ai(prompt)
            if result:
                return self._parse_result(result, backtest_result)
        except Exception as e:
            logger.error(f"回测AI分析失败: {e}")
        
        return self._local_backtest_analysis(backtest_result)
    
    def optimize_params(self, strategy_name: str, current_params: Dict, 
                       backtest_results: List[Dict]) -> Dict:
        """优化策略参数"""
        # 简单参数优化逻辑
        best_result = max(backtest_results, key=lambda x: x.get('sharpe', 0))
        
        if not self.enabled:
            return {
                "recommended_params": best_result.get('params', {}),
                "expected_sharpe": best_result.get('sharpe', 0),
                "expected_return": best_result.get('annual_return', 0),
                "analysis_method": "local"
            }
        
        try:
            prompt = self._build_optimize_prompt(strategy_name, current_params, backtest_results)
            result = self._call_ai(prompt)
            if result:
                return self._parse_optimize(result, best_result)
        except Exception as e:
            logger.error(f"参数优化失败: {e}")
        
        return {
            "recommended_params": best_result.get('params', {}),
            "expected_sharpe": best_result.get('sharpe', 0),
            "analysis_method": "local"
        }
    
    def compare_strategies(self, strategies: List[Dict]) -> Dict:
        """对比多个策略"""
        if not self.enabled:
            return self._local_strategy_comparison(strategies)
        
        try:
            prompt = self._build_compare_prompt(strategies)
            result = self._call_ai(prompt)
            if result:
                return self._parse_compare(result, strategies)
        except Exception as e:
            logger.error(f"策略对比失败: {e}")
        
        return self._local_strategy_comparison(strategies)
    
    def _build_backtest_prompt(self, bt: Dict) -> str:
        """构建回测分析提示词"""
        trades = bt.get('trades', [])
        recent_trades = trades[-10:] if trades else []
        trades_str = "\n".join([
            f"- {t.get('date', '')}: {t.get('action', '')} {t.get('symbol', '')}, 收益: {t.get('return', 0):.2f}%"
            for t in recent_trades
        ]) if recent_trades else "无交易记录"
        
        return f"""作为资深量化分析师，请分析以下回测结果。

【收益表现】
- 总收益率: {bt.get('total_return', 0):.2f}%
- 年化收益: {bt.get('annual_return', 0):.2f}%
- 基准收益: {bt.get('benchmark_return', 0):.2f}%
- 超额收益: {bt.get('excess_return', 0):.2f}%

【风险指标】
- 最大回撤: {bt.get('max_drawdown', 0):.2f}%
- 夏普比率: {bt.get('sharpe', 0):.2f}
- 卡玛比率: {bt.get('calmar', 0):.2f}
- 波动率: {bt.get('volatility', 0):.2f}%

【交易分析】
- 交易次数: {bt.get('trade_count', 0)}
- 胜率: {bt.get('win_rate', 0):.1f}%
- 盈利次数: {bt.get('win_count', 0)}
- 亏损次数: {bt.get('loss_count', 0)}
- 平均持仓天数: {bt.get('avg_holding_days', 0)}
- 平均盈利: {bt.get('avg_win', 0):.2f}%
- 平均亏损: {bt.get('avg_loss', 0):.2f}%

【最近交易】
{trades_str}

请返回JSON格式的分析报告:
{{
    "策略评分": "75/100",
    "收益评分": 80,
    "风险评分": 70,
    "稳定性评分": 75,
    "优点": ["优点1", "优点2"],
    "问题": ["问题1"],
    "优化建议": ["建议1", "建议2"],
    "风险提示": "提示内容",
    "适合市场": "牛市/熊市/震荡市/全市场"
}}

只返回JSON，不要其他内容。"""
    
    def _build_optimize_prompt(self, strategy: str, current: Dict, 
                               results: List[Dict]) -> str:
        """构建参数优化提示词"""
        results_str = "\n".join([
            f"- 参数{r.get('params', {})}: 夏普={r.get('sharpe', 0):.2f}, 年化={r.get('annual_return', 0):.2f}%, 回撤={r.get('max_drawdown', 0):.2f}%"
            for r in results[:5]
        ])
        
        return f"""作为量化策略专家，请为以下策略推荐最优参数。

【策略名称】{strategy}
【当前参数】{json.dumps(current, ensure_ascii=False)}

【参数回测结果】
{results_str}

请返回JSON格式的优化建议:
{{
    "recommended_params": {{"param1": value1, "param2": value2}},
    "expected_sharpe": 1.35,
    "expected_return": "15.5%",
    "expected_drawdown": "-12%",
    "推荐理由": "简单说明",
    "注意事项": "注意事项"
}}

只返回JSON，不要其他内容。"""
    
    def _build_compare_prompt(self, strategies: List[Dict]) -> str:
        """构建策略对比提示词"""
        strategies_str = "\n".join([
            f"""
{i}. {s.get('name', '策略'+str(i))}
   - 年化收益: {s.get('annual_return', 0):.2f}%
   - 夏普比率: {s.get('sharpe', 0):.2f}
   - 最大回撤: {s.get('max_drawdown', 0):.2f}%
   - 胜率: {s.get('win_rate', 0):.1f}%
"""
            for i, s in enumerate(strategies, 1)
        ])
        
        return f"""作为量化策略专家，请对比分析以下策略。

{strategies_str}

请返回JSON格式的对比报告:
{{
    "推荐策略": "策略名称",
    "对比结论": "总体结论",
    "各策略评分": {{
        "策略1": {{"评分": 80, "优势": [], "劣势": []}},
        "策略2": {{"评分": 75, "优势": [], "劣势": []}}
    }},
    "投资建议": "建议"
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
    
    def _parse_result(self, ai_text: str, bt: Dict) -> Dict:
        """解析AI返回结果"""
        try:
            json_match = re.search(r'\{[^{}]*\}', ai_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result['_ai_analysis'] = True
                result['backtest_summary'] = {
                    'total_return': bt.get('total_return', 0),
                    'annual_return': bt.get('annual_return', 0),
                    'sharpe': bt.get('sharpe', 0),
                    'max_drawdown': bt.get('max_drawdown', 0)
                }
                result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
                return result
        except Exception as e:
            logger.error(f"解析AI结果失败: {e}")
        
        return self._local_backtest_analysis(bt)
    
    def _parse_optimize(self, ai_text: str, best_result: Dict) -> Dict:
        """解析优化建议"""
        try:
            json_match = re.search(r'\{[^{}]*\}', ai_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result['_ai_analysis'] = True
                result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
                return result
        except Exception as e:
            logger.error(f"解析优化建议失败: {e}")
        
        return {
            "recommended_params": best_result.get('params', {}),
            "expected_sharpe": best_result.get('sharpe', 0),
            "analysis_method": "local"
        }
    
    def _parse_compare(self, ai_text: str, strategies: List[Dict]) -> Dict:
        """解析策略对比"""
        try:
            json_match = re.search(r'\{[^{}]*\}', ai_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result['_ai_analysis'] = True
                result['strategies_count'] = len(strategies)
                result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
                return result
        except Exception as e:
            logger.error(f"解析对比结果失败: {e}")
        
        return self._local_strategy_comparison(strategies)
    
    def _local_backtest_analysis(self, bt: Dict) -> Dict:
        """本地回测分析"""
        score = 60
        
        if bt.get('sharpe', 0) > 1:
            score += 15
        if abs(bt.get('max_drawdown', 100)) < 20:
            score += 10
        if bt.get('win_rate', 0) > 50:
            score += 10
        
        return {
            "策略评分": f"{min(score, 100)}/100",
            "收益评分": score,
            "风险评分": 100 - abs(bt.get('max_drawdown', 0)),
            "优点": ["收益稳定"] if score > 70 else ["待优化"],
            "问题": ["回撤较大"],
            "优化建议": ["建议优化参数"],
            "analysis_method": "local"
        }
    
    def _local_strategy_comparison(self, strategies: List[Dict]) -> Dict:
        """本地策略对比"""
        if not strategies:
            return {"error": "无策略数据"}
        
        # 按夏普比率排序
        sorted_strategies = sorted(strategies, key=lambda x: x.get('sharpe', 0), reverse=True)
        best = sorted_strategies[0]
        
        return {
            "推荐策略": best.get('name', '策略1'),
            "对比结论": "基于风险调整收益分析",
            "投资建议": "建议使用推荐策略",
            "analysis_method": "local"
        }


# 单例
_backtest_analysis_service = BacktestAnalysisService()


def get_backtest_analysis_service() -> BacktestAnalysisService:
    return _backtest_analysis_service


def analyze_backtest_with_ai(backtest_result: Dict) -> Dict:
    return _backtest_analysis_service.analyze_backtest(backtest_result)


def optimize_strategy_params(strategy_name: str, current_params: Dict,
                             backtest_results: List[Dict]) -> Dict:
    return _backtest_analysis_service.optimize_params(strategy_name, current_params, backtest_results)


def compare_strategies_with_ai(strategies: List[Dict]) -> Dict:
    return _backtest_analysis_service.compare_strategies(strategies)
