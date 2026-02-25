# services/factor_library.py
# 专业因子库定义 - 扩展版 (50+因子)

FACTOR_CATEGORIES = {
    'valuation': {
        'name': '估值因子',
        'icon': '💰',
        'description': '反映股票估值水平的指标',
        'factors': [
            {
                'key': 'pe',
                'name': '市盈率PE',
                'type': 'range',
                'direction': -1,
                'min': 0,
                'max': 200,
                'defaultMin': 0,
                'defaultMax': 50,
                'unit': '倍',
                'description': '市盈率，越低可能越被低估'
            },
            {
                'key': 'pb',
                'name': '市净率PB',
                'type': 'range',
                'direction': -1,
                'min': 0,
                'max': 50,
                'defaultMin': 0,
                'defaultMax': 5,
                'unit': '倍',
                'description': '市净率'
            },
            {
                'key': 'ps',
                'name': '市销率PS',
                'type': 'range',
                'direction': -1,
                'min': 0,
                'max': 100,
                'defaultMin': 0,
                'defaultMax': 10,
                'unit': '倍',
                'description': '市销率'
            },
            {
                'key': 'dividend_yield',
                'name': '股息率',
                'type': 'range',
                'direction': 1,
                'min': 0,
                'max': 20,
                'defaultMin': 1,
                'defaultMax': 8,
                'unit': '%',
                'description': '分红收益率'
            },
            {
                'key': 'pcf',
                'name': '市现率PCF',
                'type': 'range',
                'direction': -1,
                'min': 0,
                'max': 100,
                'defaultMin': 0,
                'defaultMax': 20,
                'unit': '倍',
                'description': '股价/每股现金流'
            }
        ]
    },
    'momentum': {
        'name': '动量因子',
        'icon': '🚀',
        'description': '反映价格趋势和动量特征',
        'factors': [
            {
                'key': 'change_5d',
                'name': '5日涨跌幅',
                'type': 'range',
                'direction': 1,
                'min': -30,
                'max': 30,
                'defaultMin': -10,
                'defaultMax': 10,
                'unit': '%',
                'description': '过去5个交易日收益率'
            },
            {
                'key': 'change_20d',
                'name': '20日涨跌幅',
                'type': 'range',
                'direction': 1,
                'min': -50,
                'max': 50,
                'defaultMin': -20,
                'defaultMax': 20,
                'unit': '%',
                'description': '过去20个交易日收益率'
            },
            {
                'key': 'change_60d',
                'name': '60日涨跌幅',
                'type': 'range',
                'direction': 1,
                'min': -80,
                'max': 80,
                'defaultMin': -30,
                'defaultMax': 30,
                'unit': '%',
                'description': '过去60个交易日收益率'
            },
            {
                'key': 'mom_1m',
                'name': '1月动量',
                'type': 'range',
                'direction': 1,
                'min': -40,
                'max': 40,
                'defaultMin': -15,
                'defaultMax': 15,
                'unit': '%',
                'description': '近1个月收益率'
            },
            {
                'key': 'mom_3m',
                'name': '3月动量',
                'type': 'range',
                'direction': 1,
                'min': -60,
                'max': 60,
                'defaultMin': -25,
                'defaultMax': 25,
                'unit': '%',
                'description': '近3个月收益率'
            },
            {
                'key': 'high_52w_ratio',
                'name': '52周新高比',
                'type': 'range',
                'direction': 1,
                'min': 0,
                'max': 120,
                'defaultMin': 50,
                'defaultMax': 100,
                'unit': '%',
                'description': '当前价格/52周最高价'
            },
            {
                'key': 'mom_accel',
                'name': '动量加速度',
                'type': 'range',
                'direction': 1,
                'min': -30,
                'max': 30,
                'defaultMin': -10,
                'defaultMax': 10,
                'unit': '%',
                'description': '短期动量-长期动量'
            }
        ]
    },
    'quality': {
        'name': '质量因子',
        'icon': '💎',
        'description': '反映公司盈利质量和财务健康',
        'factors': [
            {
                'key': 'roe',
                'name': '净资产收益率ROE',
                'type': 'range',
                'direction': 1,
                'min': -50,
                'max': 50,
                'defaultMin': 5,
                'defaultMax': 30,
                'unit': '%',
                'description': 'ROE'
            },
            {
                'key': 'roa',
                'name': '总资产收益率ROA',
                'type': 'range',
                'direction': 1,
                'min': -30,
                'max': 30,
                'defaultMin': 3,
                'defaultMax': 20,
                'unit': '%',
                'description': 'ROA'
            },
            {
                'key': 'gross_margin',
                'name': '毛利率',
                'type': 'range',
                'direction': 1,
                'min': 0,
                'max': 100,
                'defaultMin': 10,
                'defaultMax': 60,
                'unit': '%',
                'description': '毛利率'
            },
            {
                'key': 'net_profit_margin',
                'name': '净利率',
                'type': 'range',
                'direction': 1,
                'min': -50,
                'max': 50,
                'defaultMin': 0,
                'defaultMax': 30,
                'unit': '%',
                'description': '净利率'
            },
            {
                'key': 'asset_turnover',
                'name': '资产周转率',
                'type': 'range',
                'direction': 1,
                'min': 0,
                'max': 3,
                'defaultMin': 0.3,
                'defaultMax': 1.5,
                'unit': '次',
                'description': '营收/总资产'
            }
        ]
    },
    'growth': {
        'name': '成长因子',
        'icon': '🌱',
        'description': '反映公司成长性',
        'factors': [
            {
                'key': 'revenue_growth',
                'name': '营收增长率',
                'type': 'range',
                'direction': 1,
                'min': -50,
                'max': 100,
                'defaultMin': 0,
                'defaultMax': 30,
                'unit': '%',
                'description': '营收同比增长'
            },
            {
                'key': 'profit_growth',
                'name': '净利润增长率',
                'type': 'range',
                'direction': 1,
                'min': -100,
                'max': 200,
                'defaultMin': 0,
                'defaultMax': 30,
                'unit': '%',
                'description': '净利润同比增长'
            },
            {
                'key': 'revenue_cagr_3y',
                'name': '营收3年CAGR',
                'type': 'range',
                'direction': 1,
                'min': -30,
                'max': 50,
                'defaultMin': 5,
                'defaultMax': 20,
                'unit': '%',
                'description': '3年复合增长'
            },
            {
                'key': 'profit_cagr_3y',
                'name': '利润3年CAGR',
                'type': 'range',
                'direction': 1,
                'min': -50,
                'max': 100,
                'defaultMin': 5,
                'defaultMax': 30,
                'unit': '%',
                'description': '3年复合增长'
            }
        ]
    },
    'volatility': {
        'name': '波动因子',
        'icon': '📈',
        'description': '反映价格波动特征',
        'factors': [
            {
                'key': 'volatility',
                'name': '波动率',
                'type': 'range',
                'direction': -1,
                'min': 0,
                'max': 100,
                'defaultMin': 0,
                'defaultMax': 35,
                'unit': '%',
                'description': '20日收益率标准差'
            },
            {
                'key': 'atr',
                'name': 'ATR',
                'type': 'range',
                'direction': -1,
                'min': 0,
                'max': 20,
                'defaultMin': 0,
                'defaultMax': 5,
                'unit': '元',
                'description': '平均真实波幅'
            },
            {
                'key': 'max_drawdown',
                'name': '最大回撤',
                'type': 'range',
                'direction': -1,
                'min': 0,
                'max': 60,
                'defaultMin': 0,
                'defaultMax': 20,
                'unit': '%',
                'description': '20日最大回撤'
            },
            {
                'key': 'downside_vol',
                'name': '下行波动率',
                'type': 'range',
                'direction': -1,
                'min': 0,
                'max': 80,
                'defaultMin': 0,
                'defaultMax': 25,
                'unit': '%',
                'description': '负收益波动'
            }
        ]
    },
    'technical': {
        'name': '技术因子',
        'icon': '📉',
        'description': '技术分析指标',
        'factors': [
            {
                'key': 'rsi',
                'name': 'RSI',
                'type': 'range',
                'direction': 0,
                'min': 0,
                'max': 100,
                'defaultMin': 30,
                'defaultMax': 70,
                'unit': '',
                'description': '相对强弱指数'
            },
            {
                'key': 'macd',
                'name': 'MACD',
                'type': 'range',
                'direction': 1,
                'min': -5,
                'max': 5,
                'defaultMin': -1,
                'defaultMax': 1,
                'unit': '',
                'description': 'MACD柱状图'
            },
            {
                'key': 'ma_bull',
                'name': '均线多头',
                'type': 'range',
                'direction': 1,
                'min': 0,
                'max': 1,
                'defaultMin': 1,
                'defaultMax': 1,
                'unit': '',
                'description': 'MA5>MA10>MA20'
            }
        ]
    },
    'sentiment': {
        'name': '情绪因子',
        'icon': '🔥',
        'description': '反映市场情绪和活跃度',
        'factors': [
            {
                'key': 'turnover_rate',
                'name': '换手率',
                'type': 'range',
                'direction': -1,
                'min': 0,
                'max': 50,
                'defaultMin': 0,
                'defaultMax': 15,
                'unit': '%',
                'description': '20日均换手率'
            },
            {
                'key': 'turnover_change',
                'name': '换手率变化',
                'type': 'range',
                'direction': 1,
                'min': -50,
                'max': 100,
                'defaultMin': -20,
                'defaultMax': 30,
                'unit': '%',
                'description': '换手率变化率'
            },
            {
                'key': 'volume_ratio',
                'name': '量比',
                'type': 'range',
                'direction': 1,
                'min': 0,
                'max': 10,
                'defaultMin': 0.5,
                'defaultMax': 3,
                'unit': '倍',
                'description': '当前成交量/5日均量'
            }
        ]
    },
    'scale': {
        'name': '规模因子',
        'icon': '📊',
        'description': '反映公司规模',
        'factors': [
            {
                'key': 'market_cap',
                'name': '总市值',
                'type': 'range',
                'direction': 1,
                'min': 0,
                'max': 50000,
                'defaultMin': 0,
                'defaultMax': 5000,
                'unit': '亿元',
                'description': '公司总市值'
            },
            {
                'key': 'circulating_cap',
                'name': '流通市值',
                'type': 'range',
                'direction': 1,
                'min': 0,
                'max': 50000,
                'defaultMin': 0,
                'defaultMax': 2000,
                'unit': '亿元',
                'description': '流通股市值'
            },
            {
                'key': 'total_shares',
                'name': '总股本',
                'type': 'range',
                'direction': 1,
                'min': 0,
                'max': 1000,
                'defaultMin': 0,
                'defaultMax': 100,
                'unit': '亿股',
                'description': '总股本'
            }
        ]
    }
}

# 快捷筛选预设
QUICK_FILTERS = {
    'value': {
        'name': '价值投资',
        'icon': '💰',
        'description': '低PE、低PB、高股息',
        'factors': {
            'pe': [0, 20],
            'pb': [0, 3],
            'dividend_yield': [2, 10]
        }
    },
    'growth': {
        'name': '成长投资',
        'icon': '🌱',
        'description': '高增长、合理估值',
        'factors': {
            'revenue_growth': [15, 100],
            'profit_growth': [15, 100],
            'pe': [0, 50]
        }
    },
    'quality': {
        'name': '质量投资',
        'icon': '💎',
        'description': '高ROE、稳定盈利',
        'factors': {
            'roe': [15, 50],
            'roa': [8, 30],
            'gross_margin': [30, 80]
        }
    },
    'momentum': {
        'name': '动量投资',
        'icon': '🚀',
        'description': '趋势向上、量价齐升',
        'factors': {
            'mom_1m': [5, 40],
            'mom_3m': [10, 60],
            'rsi': [50, 80],
            'turnover_rate': [3, 20]
        }
    },
    'low_vol': {
        'name': '低波动',
        'icon': '🛡️',
        'description': '低波动、稳健收益',
        'factors': {
            'volatility': [0, 25],
            'max_drawdown': [0, 15],
            'beta': [0, 1]
        }
    },
    'small_cap': {
        'name': '小盘成长',
        'icon': '📊',
        'description': '小市值、高成长',
        'factors': {
            'market_cap': [0, 300],
            'revenue_growth': [20, 100],
            'mom_3m': [5, 50]
        }
    },
    'blue_chip': {
        'name': '蓝筹白马',
        'icon': '🏆',
        'description': '大盘蓝筹、业绩稳定',
        'factors': {
            'market_cap': [1000, 50000],
            'roe': [12, 50],
            'profit_growth': [5, 50],
            'volatility': [0, 30]
        }
    }
}
