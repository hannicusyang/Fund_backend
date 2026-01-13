# app.py
import os
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

# ====== 你的配置 ======
from config import DB_URL, logger

# ====== 你的任务模块 ======
from task.fund_estimation_scheduler import fetch_and_save_fund_estimation, init_fund_estimation_table
from task.fund_open_daily import fund_open_synchronization
from task.fund_history_to_mysql import fetch_and_save_fund_history

app = Flask(__name__)

# ====== （可选）如果你要用 SQLAlchemy ======
# from flask_sqlalchemy import SQLAlchemy
# app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# db = SQLAlchemy(app)
# with app.app_context():
#     db.create_all()

# ====== 初始化你的表（用你自己的逻辑）======
init_fund_estimation_table()

# ====== 调度器（保持原样）======
scheduler = BackgroundScheduler()
scheduler.add_job(fund_open_synchronization, 'cron', id='fund_open_sync', hour=0, minute=30)
scheduler.add_job(fetch_and_save_fund_estimation, trigger=IntervalTrigger(minutes=3), id='fund_estimation_job', replace_existing=True)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ====== 路由（保持原样）======
@app.route('/run-task')
def manual_run():
    return {"status": "项目正常运行"}

@app.route('/openfund-update')
def openfund_update():
    fund_open_synchronization()
    return {"status": "开放型基金信息已更新"}

@app.route("/fund/history/<fund_code>")
def api_fetch_fund(fund_code: str):
    result = fetch_and_save_fund_history(fund_code, force_update=True)
    return result

@app.route('/debug/fetch_es_debug')
def debug_es_fetch():
    fetch_and_save_fund_estimation(is_debug=True)
    return {"status": "success", "message": "手动抓取已触发"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)