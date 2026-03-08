# app.py
import os
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
from models import db
from config import AppConfig
from config.env_config import config
from flask_cors import CORS

from routes.my_fund_holding import holding_bp
from routes.fund_lab import fund_lab_bp
from routes.fund_backtest import fund_backtest_bp
from routes.auth import auth_bp  # 用户认证
from routes.monitor import monitor_bp  # 资讯监控
from routes.manual_monitor import manual_bp  # 手动添加监控
# ====== 您的任务模块（先不导入 sync_fund_holdings_quarterly）======
from tasks.fund_basic_sync import sync_fund_basic_info
from tasks.fund_estimation_scheduler import fetch_and_save_fund_estimation
from tasks.fund_open_daily import fund_open_synchronization
from tasks.fund_history_to_mysql import fetch_and_save_fund_history
from tasks.fund_history_to_mysql import sync_all_watched_funds
from tasks.sync_stock_market_overview import sync_all_stock_overview
from tasks.sync_stock_realtime import sync_stock_realtime
from tasks.sync_stock_screening import sync_stock_screening_data  # ← 新增股票实时行情同步
# from tasks.data_collection import run_data_collection  # ← 延迟导入避免循环

app = Flask(__name__, static_folder=None)

# 添加静态文件路由用于B站登录二维码
@app.route('/bilibili_login_qr.png')
def serve_qr():
    from flask import send_file
    qr_path = '/home/clawdbot/.openclaw/workspace/bilibili_login_qr.png'
    if os.path.exists(qr_path):
        return send_file(qr_path, mimetype='image/png')
    return "QR码不存在", 404

CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
app.config.from_object(AppConfig)

# ====== 初始化数据库 ======
db.init_app(app)
with app.app_context():
    db.create_all()



# ====== 调度器（关键修改：延迟导入季度持仓任务）======
scheduler = BackgroundScheduler()

# 每天凌晨 0:10 执行
scheduler.add_job(sync_fund_basic_info, 'cron', hour=0, minute=10)
scheduler.add_job(fund_open_synchronization, 'cron', id='fund_open_sync', hour=0, minute=30)
scheduler.add_job(fetch_and_save_fund_estimation, trigger=IntervalTrigger(minutes=3), id='fund_estimation_job', replace_existing=True,max_instances=2)
scheduler.add_job(sync_all_watched_funds, 'cron', id='fund_watched_sync', hour=0, minute=40)

# 启动监控任务调度器
from services.monitor.scheduler import init_scheduler
init_scheduler(app)
scheduler.add_job(sync_all_stock_overview, 'cron', hour=16, minute=30)
scheduler.add_job(sync_stock_realtime, trigger=IntervalTrigger(minutes=1), id='stock_realtime_job', replace_existing=True, max_instances=1)  # ← 每分钟同步股票实时行情
scheduler.add_job(sync_stock_screening_data, 'cron', hour=16, minute=35)  # ← 每日收盘后同步多因子筛选数据

# 每天凌晨4点采集股票因子数据（延迟导入避免循环）
def run_stock_data_collection():
    from tasks.data_collection import run_data_collection
    run_data_collection()
scheduler.add_job(run_stock_data_collection, 'cron', hour=4, minute=0)  # ← 每天凌晨4点采集

# 每天凌晨2点同步波动率数据（用字符串引用避免循环导入）
def run_sync_volatility():
    from tasks.sync_stock_volatility import sync_all_volatility
    sync_all_volatility()
scheduler.add_job(run_sync_volatility, 'cron', hour=2, minute=0)  # ← 每日凌晨2点同步波动率数据


# ✅ 关键修复：在这里局部导入，避免顶层循环
scheduler.add_job(
    id='sync_fund_holdings_q1',
    func= 'tasks.sync_fund_holdings_quarterly:sync_watchlist_fund_holdings_quarterly',
    trigger='cron',
    month='1,4,7,10',
    day=15,
    hour=2,
    minute=0
)

# 凌晨1点全量同步股票数据（用字符串引用避免循环导入）
def run_sync_all_stock():
    from tasks.sync_all_stock_data import main
    main()

scheduler.add_job(run_sync_all_stock, 'cron', hour=1, minute=0)

# 每天凌晨2点同步指数历史数据
def run_sync_index_history():
    from tasks.sync_index_history import sync_index_history_data
    sync_index_history_data()

scheduler.add_job(run_sync_index_history, 'cron', hour=2, minute=30)

# 每天凌晨3点同步基金历史净值
def run_sync_fund_history():
    from tasks.fund_history_to_mysql import sync_fund_history
    sync_fund_history()

scheduler.add_job(run_sync_fund_history, 'cron', hour=3, minute=0)

scheduler.start()
atexit.register(lambda: scheduler.shutdown())


# ====== 注册蓝图 ======
from routes.watchlist import watchlist_bp
from routes.fund_rank import fund_rank_bp
from routes.fund_detail import fund_detail_bp
from routes.stock_market_overview import stock_overview_bp
from routes.stock_watchlist import stock_watchlist_bp
from routes.stock_realtime import stock_realtime_bp
from routes.stock_screening import stock_screening_bp
from routes.stock_kline import stock_kline_bp
from routes.stock_factor_api import stock_factor_bp  # ← 新增多因子API
from routes.stock_backtest import stock_backtest_bp  # 股票回测API
from routes.stock_backtest_pro import stock_backtest_pro_bp  # 专业回测API
from routes.stock_strategy_api import stock_strategy_bp  # 策略持久化API
from routes.market_intelligence import market_intelligence_bp  # 市场资讯API

app.register_blueprint(watchlist_bp, url_prefix='/api/watchlist')
app.register_blueprint(fund_rank_bp, url_prefix='/api/funds')
app.register_blueprint(holding_bp, url_prefix='/api/holding')
app.register_blueprint(fund_detail_bp, url_prefix='/api/fund_detail')
app.register_blueprint(stock_overview_bp, url_prefix='/api/stock')
app.register_blueprint(stock_watchlist_bp, url_prefix='/api/stock/watchlist')
app.register_blueprint(stock_realtime_bp, url_prefix='/api/stock')
app.register_blueprint(stock_factor_bp)  # 专业版多因子API
app.register_blueprint(stock_screening_bp)  # 多因子选股API
app.register_blueprint(stock_kline_bp, url_prefix='/api/stock')  # K线数据API
app.register_blueprint(fund_lab_bp, url_prefix='/api/lab')
app.register_blueprint(fund_backtest_bp, url_prefix='/api/backtest')
app.register_blueprint(auth_bp)  # 用户认证API
app.register_blueprint(stock_backtest_bp, url_prefix='/api/stock')  # 股票回测API
app.register_blueprint(stock_backtest_pro_bp, url_prefix='/api/stock')  # 专业回测API
app.register_blueprint(stock_strategy_bp, url_prefix='/api/strategy')  # 策略持久化API
app.register_blueprint(market_intelligence_bp)  # 市场资讯API
app.register_blueprint(monitor_bp, url_prefix='/api/monitor')  # 资讯监控API
app.register_blueprint(manual_bp, url_prefix='/api/manual')  # 手动添加API
# ====== 路由（保持原样）======
@app.route('/api/run-task')
def manual_run():
    return {"status": "项目正常运行"}

@app.route('/api/openfund-update')
def openfund_update():
    fund_open_synchronization()
    return {"status": "开放型基金信息已更新"}

@app.route("/api//fund/history/<fund_code>")
def api_fetch_fund(fund_code: str):
    result = fetch_and_save_fund_history(fund_code, force_update=True)
    return jsonify(result)

@app.route('/api/debug/fetch_es_debug')
def debug_es_fetch():
    fetch_and_save_fund_estimation(is_debug=True)
    return {"status": "success", "message": "手动抓取已触发"}

@app.route('/api/debug/sync_fund_basic_info')
def debug_sync_fund_basic_info():
    sync_fund_basic_info()
    return {"status": "success", "message": "基金基本信息已同步"}

if __name__ == '__main__':
    app.run(host=config['HOST'], port=config['PORT'], debug=False)