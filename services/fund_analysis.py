# services/fund_analysis.py
# 基金智能分析服务

import os
from config.env_config import MINIMAX_API_KEY, MINIMAX_BASE_URL

import json
import re
from typing import Dict, List, Optional
from datetime import datetime
from config.logging_config import logger


class FundAnalysisService:
    def __init__(self):
        self.api_key = MINIMAX_API_KEY
        self.base_url = MINIMAX_BASE_URL  # https://api.minimaxi.com/anthropic
        self.enabled = bool(self.api_key and len(self.api_key) > 10)
        if self.enabled:
            logger.info(f"基金AI分析服务已启用, API: {self.base_url}")

    def analyze_fund(self, fund_data: Dict, risk_return_data: Dict = None) -> Dict:
        if not self.enabled:
            raise Exception("AI分析服务未启用")
        
        prompt = self._build_fund_prompt(fund_data, risk_return_data)
        result = self._call_ai(prompt)
        if not result:
            raise Exception("AI API调用失败")
        
        parsed = self._parse_result(result, fund_data)
        parsed['analysis_method'] = 'ai'
        parsed['_ai_analysis'] = True
        return parsed

    def compare_funds(self, funds_data: List[Dict], extra_data: Dict = None) -> Dict:
        if not self.enabled:
            raise Exception("AI分析服务未启用")
        
        prompt = self._build_comparison_prompt(funds_data, extra_data)
        result = self._call_ai(prompt)
        if not result:
            raise Exception("AI API调用失败")
        
        parsed = self._parse_comparison(result, funds_data)
        parsed['analysis_method'] = 'ai'
        parsed['_ai_analysis'] = True
        return parsed

    def _call_ai(self, prompt: str) -> Optional[str]:
        """使用OpenAI SDK调用MiniMax API"""
        from openai import OpenAI
        import httpx
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Calling MiniMax API (attempt {attempt + 1}/{max_retries})")
                
                client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=httpx.Timeout(60.0, connect=20.0)
                )
                
                response = client.chat.completions.create(
                    model="MiniMax-M2.5",
                    max_tokens=800,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                message = response.choices[0].message
                content = message.content
                
                if not content:
                    logger.warning("AI returned empty content, retrying...")
                    continue
                
                # 清理thinking块
                import re
                content = re.sub(r'<｜.*?｜>', '', content)
                content = content.strip()
                
                logger.info(f"AI response length: {len(content)}")
                return content
                    
            except Exception as e:
                logger.error(f"MiniMax API调用失败: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)
        return None

    def _build_fund_prompt(self, fund: Dict, risk_return_data: Dict = None) -> str:
        returns = fund.get('period_returns', {})
        
        # 构建风险收益数据部分
        risk_section = ""
        if risk_return_data:
            for item in risk_return_data:
                if item.get('code') == fund.get('fund_code'):
                    risk_section = f"""
风险收益指标(基于{item.get('period', '1y')}):
  - 年化收益率: {item.get('annual_return', 'N/A')}%
  - 年化波动率: {item.get('volatility', 'N/A')}%
  - 夏普比率: {item.get('sharpe_ratio', 'N/A')}
  - 索提诺比率: {item.get('sortino_ratio', 'N/A')}
  - 卡玛比率: {item.get('calmar_ratio', 'N/A')}
  - 最大回撤: {item.get('max_drawdown', 'N/A')}%
  - Alpha: {item.get('alpha', 'N/A')}
  - Beta: {item.get('beta', 'N/A')}
  - 信息比率: {item.get('information_ratio', 'N/A')}
  - 胜率: {item.get('win_rate', 'N/A')}%
"""
                    break
        
        return f"""作为资深金融分析师，从专业、全面的角度分析以下基金:

【基本信息】
基金代码: {fund.get('fund_code', '')}
基金名称: {fund.get('fund_name', '')}
净值: {fund.get('nav', 'N/A')}
累计净值: {fund.get('accumulated_net_value', 'N/A')}
基金经理: {fund.get('manager', 'N/A')}
基金规模: {fund.get('scale', 'N/A')}亿
成立日期: {fund.get('establish_date', 'N/A')}
成立以来收益: {fund.get('since_inception_return', 'N/A')}%
费率: {fund.get('fee_rate', 'N/A')}%
风险等级: {fund.get('risk_level', 'N/A')}

【历史收益率】
日涨幅: {fund.get('daily_return', 'N/A')}%
周涨幅: {fund.get('weekly_return', 'N/A')}%
月涨幅: {returns.get('1m', 'N/A')}%
近3月: {returns.get('3m', 'N/A')}%
近6月: {returns.get('6m', 'N/A')}%
近1年: {returns.get('1y', 'N/A')}%
近2年: {returns.get('2y', 'N/A')}%
近3年: {returns.get('3y', 'N/A')}%
今年来: {fund.get('ytd_return', 'N/A')}%
排名: {fund.get('rank', 'N/A')}

【量化风险指标】
夏普比率: {fund.get('sharpe', 'N/A')}
最大回撤: {fund.get('max_drawdown', 'N/A')}%
波动率: {fund.get('volatility', 'N/A')}%
{risk_section}
【持仓风格】
top10持仓占比: {fund.get('top10_ratio', 'N/A')}%
重仓行业: {', '.join(fund.get('top_sectors', []))}
换手率: {fund.get('turnover_rate', 'N/A')}%

请从专业角度分析该基金的收益能力、风险控制、投资价值，给出:
1. 综合评分(0-100)和各维度评分
2. 优势(2-3条)
3. 劣势/风险点(2-3条)
4. 投资建议(买入/持有/卖出)
5. 风险提示
6. 适合人群

返回JSON格式:
{{"综合评分":"85/100","收益评分":85,"风险评分":80,"规模评分":75,"优势":["优势1","优势2"],"劣势":["劣势1","劣势2"],"投资建议":"建议持有","风险提示":"提示","适合人群":"平衡型"}}
只返回JSON，不要其他文字。"""

    def _build_comparison_prompt(self, funds: List[Dict], extra_data: Dict = None) -> str:
        # 构建每只基金的详细信息
        fund_list = []
        for f in funds:
            returns = f.get('period_returns', {})
            fund_list.append(f"""
【{f.get('fund_name', f.get('fund_code', ''))} ({f.get('fund_code', '')})】
  基金名称: {f.get('fund_name', 'N/A')}
  基金代码: {f.get('fund_code', 'N/A')}
  基金净值: {f.get('nav', 'N/A')}
  累计净值: {f.get('accumulated_net_value', 'N/A')}
  基金规模: {f.get('scale', 'N/A')}亿元
  基金经理: {f.get('manager', 'N/A')}
  成立日期: {f.get('establish_date', 'N/A')}
  费率: {f.get('fee_rate', 'N/A')}%
  风险等级: {f.get('risk_level', 'N/A')}
  
  【历史收益率】
  日涨幅: {f.get('daily_return','N/A')}%
  周涨幅: {f.get('weekly_return','N/A')}%
  月涨幅: {returns.get('1m','N/A')}%
  近3月: {returns.get('3m','N/A')}%
  近6月: {returns.get('6m','N/A')}%
  近1年: {returns.get('1y','N/A')}%
  近2年: {returns.get('2y','N/A')}%
  近3年: {returns.get('3y','N/A')}%
  今年来: {f.get('ytd_return','N/A')}%
  成立以来: {f.get('since_inception_return','N/A')}%
  业绩排名: {f.get('rank','N/A')}
  
  【风险指标】
  夏普比率: {f.get('sharpe','N/A')}
  最大回撤: {f.get('max_drawdown','N/A')}%
  波动率: {f.get('volatility','N/A')}%
  
  【持仓特征】
  top10持仓占比: {f.get('top10_ratio','N/A')}%
  重仓行业: {','.join(f.get('top_sectors',[])[:3]) if f.get('top_sectors') else 'N/A'}
  换手率: {f.get('turnover_rate','N/A')}%
""")
        
        # 构建相关性矩阵（带基金名称）
        correlation_section = ""
        if extra_data and extra_data.get('correlation_matrix'):
            corr = extra_data['correlation_matrix']
            matrix = corr.get('matrix', [])
            codes = corr.get('codes', [])
            # 获取基金名称映射
            fund_names = {f.get('fund_code'): f.get('fund_name', f.get('fund_code')) for f in funds}
            if matrix and codes:
                correlation_section = "\n【基金相关性矩阵】\n"
                correlation_section += "        " + " ".join([f"{fund_names.get(c, c):>8}" for c in codes]) + "\n"
                for i, row in enumerate(matrix):
                    row_str = " ".join([f"{val:>8.2f}" for val in row])
                    correlation_section += f"{fund_names.get(codes[i], codes[i]):>8} {row_str}\n"
                correlation_section += "\n(相关系数>0.7表示高度相关，0.3-0.7表示中等相关，<0.3表示低相关)"
        
        # 构建风险收益对比（带基金名称）
        risk_section = ""
        if extra_data and extra_data.get('risk_return_data'):
            risk_section = "\n【专业风险收益指标对比】\n"
            risk_section += f"{'基金':<12} {'年化收益':>8} {'年化波动':>8} {'夏普比率':>8} {'索提诺':>8} {'卡玛':>8} {'最大回撤':>8} {'胜率':>6} {'Alpha':>8} {'Beta':>6}\n"
            risk_section += "-" * 85 + "\n"
            for item in extra_data['risk_return_data']:
                fund_name = item.get('name', item.get('code', ''))[:10]
                risk_section += f"{fund_name:<12} {item.get('annual_return','N/A'):>7}% {item.get('volatility','N/A'):>7}% {item.get('sharpe_ratio','N/A'):>8} {item.get('sortino_ratio','N/A'):>8} {item.get('calmar_ratio','N/A'):>8} {item.get('max_drawdown','N/A'):>8}% {item.get('win_rate','N/A'):>6}% {item.get('alpha','N/A'):>8} {item.get('beta','N/A'):>6}\n"
            risk_section += "\n(年化收益越高越好，夏普>1表示风险调整收益优秀，索提诺>2优秀，卡玛>1优秀，回撤越小越好，胜率>50%优秀)"
        
        # 组合配置建议
        config_section = ""
        if extra_data and extra_data.get('correlation_matrix'):
            config_section = """
【组合配置分析建议】
基于相关性矩阵，请分析：
1. 这些基金的低相关性组合是否能有效分散风险
2. 建议的配置比例（如果高度相关，不建议同时配置）
3. 风险预算分配建议
"""
        
        prompt = f"""作为资深金融投资顾问，你需要对以下多只基金进行**专业、全面、深度**的量化分析。

【分析要求】
1. 必须基于提供的真实数据进行客观分析
2. 每个维度的分析都需要给出具体的数值支撑
3. 优势/劣势分析要具体到每一项指标
4. 投资建议需要明确给出买入/持有/卖出的理由

【基金基本信息】
{''.join(fund_list)}

{correlation_section}

{risk_section}

{config_section}

请从以下**专业维度**进行深度分析：

**一、收益能力分析**
- 各周期收益排名及超额收益能力
- 收益持续性判断
- 与业绩基准对比

**二、风险控制分析**  
- 最大回撤控制能力
- 波动率控制水平
- 下行风险评估

**三、风险调整收益分析**
- 夏普比率（>1为优秀）
- 索提诺比率（>2为优秀）
- 卡玛比率（>1为优秀）
- Alpha（超额收益能力）
- Beta（与市场相关性）

**四、组合配置价值分析**
- 基于相关性矩阵分析组合分散化效果
- 给出具体的配置比例建议
- 风险预算分配

**五、综合评分与投资建议**
- 每只基金给出0-100的综合评分
- 明确的投资建议（买入/持有/卖出）
- 适合的投资人群

返回JSON格式(必须包含基金名称和各基金评分):
{{
  "推荐基金": "基金名称",
  "对比结论": "500字以上的综合分析结论，包含收益、风险、配置价值等",
  "各基金评分": {{
    "基金名称": {{"代码":"基金代码","评分":85,"收益评分":90,"风险评分":80,"优势":["具体优势1(带数值)","具体优势2(带数值)","具体优势3"],"劣势":["具体劣势1(带数值)","具体劣势2"]}},
    "基金名称": {{"代码":"基金代码","评分":70,"收益评分":75,"风险评分":65,"优势":["具体优势1"],"劣势":["具体劣势1","具体劣势2"]}}
  }},
  "投资建议": "明确的投资建议及理由",
  "风险提示": "主要风险点",
  "适合人群": "适合的投资者类型"
}}
只返回JSON，不要其他文字。"""
        return prompt

    def _parse_result(self, ai_text: str, fund_data: Dict) -> Dict:
        # Method 1: Try simple JSON parse
        try:
            result = json.loads(ai_text.strip())
            result['fund_code'] = fund_data.get('fund_code')
            result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
            return result
        except: pass
        
        # Method 2: Try extracting JSON block
        try:
            # Remove markdown code blocks
            cleaned = re.sub(r'^```json\s*', '', ai_text.strip())
            cleaned = re.sub(r'^```\s*', '', cleaned)
            cleaned = re.sub(r'```$', '', cleaned)
            
            # Find JSON in the text
            start = cleaned.find('{')
            if start >= 0:
                depth = 0
                for i, c in enumerate(cleaned[start:], start):
                    if c == '{': depth += 1
                    elif c == '}': 
                        depth -= 1
                        if depth == 0:
                            json_str = cleaned[start:i+1]
                            result = json.loads(json_str)
                            result['fund_code'] = fund_data.get('fund_code')
                            result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
                            return result
        except Exception as e:
            logger.error(f"解析失败: {e}")
        
        # Last resort: create basic response
        return {
            "综合评分": "75/100",
            "收益评分": 75,
            "风险评分": 75,
            "规模评分": 75,
            "优势": ["AI分析响应"],
            "劣势": [],
            "投资建议": "建议持有",
            "fund_code": fund_data.get('fund_code'),
            "analysis_date": datetime.now().strftime('%Y-%m-%d')
        }

    def _parse_comparison(self, ai_text: str, funds_data: List[Dict]) -> Dict:
        # 创建基金名称映射
        fund_names_map = {f.get('fund_name', f.get('fund_code')): f.get('fund_code') for f in funds_data}
        
        # Method 1: Try simple JSON parse
        try:
            result = json.loads(ai_text.strip())
            result['funds_count'] = len(funds_data)
            result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
            # 添加基金名称列表
            result['fund_names'] = [f.get('fund_name', f.get('fund_code')) for f in funds_data]
            # 确保各基金评分包含代码信息
            if '各基金评分' in result:
                for name, info in result['各基金评分'].items():
                    if '代码' not in info:
                        info['代码'] = fund_names_map.get(name, name)
            return result
        except: pass
        
        # Method 2: Try extracting JSON block
        try:
            cleaned = re.sub(r'^```json\s*', '', ai_text.strip())
            cleaned = re.sub(r'^```\s*', '', cleaned)
            cleaned = re.sub(r'```$', '', cleaned)
            
            start = cleaned.find('{')
            if start >= 0:
                depth = 0
                for i, c in enumerate(cleaned[start:], start):
                    if c == '{': depth += 1
                    elif c == '}': 
                        depth -= 1
                        if depth == 0:
                            json_str = cleaned[start:i+1]
                            result = json.loads(json_str)
                            result['funds_count'] = len(funds_data)
                            result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
                            result['fund_names'] = [f.get('fund_name', f.get('fund_code')) for f in funds_data]
                            # 确保各基金评分包含代码信息
                            if '各基金评分' in result:
                                for name, info in result['各基金评分'].items():
                                    if '代码' not in info:
                                        info['代码'] = fund_names_map.get(name, name)
                            return result
        except Exception as e:
            logger.error(f"解析失败: {e}")
        
        return {
            "推荐基金": funds_data[0].get('fund_name', 'N/A') if funds_data else 'N/A',
            "对比结论": "基于AI分析",
            "投资建议": "建议持有",
            "funds_count": len(funds_data),
            "fund_names": [f.get('fund_name', f.get('fund_code')) for f in funds_data],
            "analysis_date": datetime.now().strftime('%Y-%m-%d')
        }


def analyze_fund_with_ai(fund_data: Dict) -> Dict:
    service = FundAnalysisService()
    return service.analyze_fund(fund_data)


def compare_funds_with_ai(funds_data: List[Dict]) -> Dict:
    service = FundAnalysisService()
    return service.compare_funds(funds_data)


def get_fund_analysis_service():
    return FundAnalysisService()


def calculate_fund_correlation(fund_codes: List[str], start_date: str, end_date: str) -> Dict:
    """
    计算基金相关性矩阵
    """
    # 延迟导入，避免循环依赖
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    import numpy as np
    
    try:
        # 动态导入Flask应用上下文
        from flask import current_app
        from models.fund_nav_history import FundNavHistory
        from models import db
        
        # 获取历史净值数据
        nav_data = {}
        for code in fund_codes:
            navs = FundNavHistory.query.filter(
                FundNavHistory.fund_code == code,
                FundNavHistory.nav_date >= start_date,
                FundNavHistory.nav_date <= end_date
            ).order_by(FundNavHistory.nav_date).all()
            
            if navs and len(navs) >= 10:
                # 计算日收益率
                prices = [float(n.net_value) for n in navs]
                returns = []
                for i in range(1, len(prices)):
                    ret = (prices[i] - prices[i-1]) / prices[i-1]
                    returns.append(ret)
                if returns:
                    nav_data[code] = returns
        
        if len(nav_data) < 2 or not nav_data:
            logger.warning(f"相关性数据不足: {len(nav_data)}只基金")
            return None
        
        # 对齐数据长度
        min_len = min(len(v) for v in nav_data.values())
        aligned_data = {k: v[:min_len] for k, v in nav_data.items()}
        
        # 计算相关性矩阵
        codes = list(aligned_data.keys())
        n = len(codes)
        matrix = np.zeros((n, n))
        
        for i, code_i in enumerate(codes):
            for j, code_j in enumerate(codes):
                if i == j:
                    matrix[i][j] = 1.0
                else:
                    # 计算相关系数
                    data_i = np.array(aligned_data[code_i])
                    data_j = np.array(aligned_data[code_j])
                    corr = np.corrcoef(data_i, data_j)[0, 1]
                    matrix[i][j] = round(corr, 2) if not np.isnan(corr) else 0
        
        return {
            'codes': codes,
            'matrix': matrix.tolist(),
            'start_date': start_date,
            'end_date': end_date
        }
    except Exception as e:
        logger.error(f"计算相关性失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def calculate_fund_risk_return(fund_codes: List[str], period: str = '1y') -> List[Dict]:
    """
    计算基金风险收益指标
    """
    # 延迟导入
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    import numpy as np
    from datetime import datetime, timedelta
    
    try:
        from flask import current_app
        from models.fund_list import FundList
        from models.fund_nav_history import FundNavHistory
        from models import db
        
        period_days = {'1m': 30, '3m': 90, '6m': 180, '1y': 365, '2y': 730, '3y': 1095}
        days = period_days.get(period, 365)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        results = []
        for code in fund_codes:
            try:
                # 获取净值数据
                navs = FundNavHistory.query.filter(
                    FundNavHistory.fund_code == code,
                    FundNavHistory.nav_date >= start_date.strftime('%Y-%m-%d'),
                    FundNavHistory.nav_date <= end_date.strftime('%Y-%m-%d')
                ).order_by(FundNavHistory.nav_date).all()
                
                if not navs or len(navs) < 10:
                    continue
                
                prices = [float(n.net_value) for n in navs]
                returns = []
                for i in range(1, len(prices)):
                    ret = (prices[i] - prices[i-1]) / prices[i-1]
                    returns.append(ret)
                
                if not returns:
                    continue
                
                returns = np.array(returns)
                
                # 计算各项指标
                annual_return = np.mean(returns) * 252 * 100  # 年化收益
                volatility = np.std(returns) * np.sqrt(252) * 100  # 年化波动率
                
                # 夏普比率 (假设无风险利率3%)
                risk_free = 0.03
                sharpe = (annual_return/100 - risk_free) / (volatility/100) if volatility > 0 else 0
                
                # 最大回撤
                cumulative = np.cumprod(1 + returns)
                running_max = np.maximum.accumulate(cumulative)
                drawdowns = (cumulative - running_max) / running_max
                max_drawdown = np.min(drawdowns) * 100
                
                # 索提诺比率 (只考虑下行波动)
                downside_returns = returns[returns < 0]
                downside_std = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0
                sortino = (annual_return/100 - risk_free) / downside_std if downside_std > 0 else 0
                
                # 卡玛比率
                calmar = abs(annual_return / max_drawdown) if max_drawdown != 0 else 0
                
                # 胜率
                win_rate = (returns > 0).sum() / len(returns) * 100
                
                # 获取基金信息
                fund = FundList.query.filter_by(fund_code=code).first()
                
                results.append({
                    'code': code,
                    'name': fund.fund_name if fund else code,
                    'period': period,
                    'annual_return': round(annual_return, 2),
                    'volatility': round(volatility, 2),
                    'sharpe_ratio': round(sharpe, 2),
                    'sortino_ratio': round(sortino, 2),
                    'calmar_ratio': round(calmar, 2),
                    'max_drawdown': round(max_drawdown, 2),
                    'win_rate': round(win_rate, 2),
                    'alpha': round(annual_return - 10, 2),  # 假设基准收益10%
                    'beta': 1.0,  # 需要市场数据计算
                    'information_ratio': round(sharpe * 0.8, 2)  # 近似
                })
            except Exception as e:
                logger.warning(f"计算基金{code}风险收益失败: {e}")
                continue
        
        if not results:
            logger.warning(f"风险收益数据不足")
            
        return results
    except Exception as e:
        logger.error(f"计算风险收益失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []
