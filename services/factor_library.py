# services/factor_library.py
# 专业因子库定义

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
            }
        ]
    },
    'momentum': {
        'name': '动量因子',
        'icon': '🚀',
        'description': '反映价格趋势和波动特征',
        'factors': [
            {
                'key': 'change_5d',
                'name': '5日涨跌幅',
                'type': 'range',
                'direction': 1,
                'min': -50,
                'max': 50,
                'defaultMin': -20,
                'defaultMax': 20,
                'unit': '%',
                'description': '过去5个交易日的收益率'
            },
            {
                'key': 'change_20d',
                'name': '20日涨跌幅',
                'type': 'range',
                'direction': 1,
                'min': -80,
                'max': 80,
                'defaultMin': -30,
                'defaultMax': 30,
                'unit': '%',
                'description': '过去20个交易日的收益率'
            },
            {
                'key': 'change_60d',
                'name': '60日涨跌幅',
                'type': 'range',
                'direction': 1,
                'min': -100,
                'max': 100,
                'defaultMin': -50,
                'defaultMax': 50,
                'unit': '%',
                'description': '过去60个交易日的收益率'
            },
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
                'description': '换手率'
            }
        ]
    },
    'quality': {
        'name': '质量因子',
        'icon': '💎',
        'description': '反映公司盈利质量和稳定性',
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
                'min': -100,
                'max': 200,
                'defaultMin': 0,
                'defaultMax': 50,
                'unit': '%',
                'description': '营业收入同比增长率'
            },
            {
                'key': 'profit_growth',
                'name': '净利润增长率',
                'type': 'range',
                'direction': 1,
                'min': -200,
                'max': 300,
                'defaultMin': 0,
                'defaultMax': 50,
                'unit': '%',
                'description': '净利润同比增长率'
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
            'pb': [0, 3]
        }
    },
    'growth': {
        'name': '成长投资',
        'icon': '🌱',
        'description': '高增长、合理估值',
        'factors': {
            'revenue_growth': [15, 100],
            'profit_growth': [15, 100]
        }
    },
    'quality': {
        'name': '质量投资',
        'icon': '💎',
        'description': '高ROE、稳定盈利',
        'factors': {
            'roe': [10, 50],
            'gross_margin': [20, 80]
        }
    },
    'momentum': {
        'name': '动量投资',
        'icon': '🚀',
        'description': '趋势向上',
        'factors': {
            'change_20d': [5, 50],
            'change_60d': [10, 80]
        }
    },
    'small_cap': {
        'name': '小盘成长',
        'icon': '📊',
        'description': '小市值、高成长',
        'factors': {
            'market_cap': [0, 300],
            'profit_growth': [20, 100]
        }
    }
}
