# app.py
import os
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
from models import db
from config import AppConfig
from flask_cors import CORS

from routes.my_fund_holding import holding_bp
# ====== 您的任务模块（先不导入 sync_fund_holdings_quarterly）======
from tasks.fund_basic_sync import sync_fund_basic_info
from tasks.fund_estimation_scheduler import fetch_and_save_fund_estimation
from tasks.fund_open_daily import fund_open_synchronization
from tasks.fund_history_to_mysql import fetch_and_save_fund_history
from tasks.fund_history_to_mysql import sync_all_watched_funds
app = Flask(__name__)
CORS(app)
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

scheduler.start()
atexit.register(lambda: scheduler.shutdown())


# ====== 注册蓝图 ======
from routes.watchlist import watchlist_bp
from routes.fund_rank import fund_rank_bp
from routes.fund_detail import fund_detail_bp
app.register_blueprint(watchlist_bp, url_prefix='/api/watchlist')
app.register_blueprint(fund_rank_bp, url_prefix='/api/funds')
app.register_blueprint(holding_bp, url_prefix='/api/holding')
app.register_blueprint(fund_detail_bp, url_prefix='/api/fund_detail')
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
    app.run(host='0.0.0.0', port=5000)