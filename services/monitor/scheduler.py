"""
定时任务调度服务 - 修复版
"""
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 数据库连接
DATABASE_URL = 'sqlite:///./fund_monitor.db'
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

# 全局调度器
scheduler = BackgroundScheduler()


def get_session():
    return Session()


def run_monitor_task(task_id):
    """执行监控任务"""
    # 使用API相同的SQLite session
    session = get_session()
    try:
        from models.monitor.models import MonitorTask, MonitorLog
        
        task = session.query(MonitorTask).get(task_id)
        if not task or not task.enabled:
            return
        
        # 记录开始日志
        log = MonitorLog(
            task_id=task_id,
            level='INFO',
            message=f'开始执行任务: {task.task_name}'
        )
        session.add(log)
        session.commit()
        
        # 根据平台执行不同的监控逻辑
        # 注意：bilibili_monitor.py 可以处理所有平台的RSS订阅
        log = MonitorLog(task_id=task_id, level='INFO', 
            message=f'🔍 检测到平台: {task.platform}')
        session.add(log)
        session.commit()
        
        if task.platform in ['bilibili', 'gelonghui', 'jin10', 'wallstreetcn', 'cls', 'caijing', 'eastmoney']:
            try:
                from services.monitor.bilibili_monitor import run_bilibili_task
                log = MonitorLog(task_id=task_id, level='INFO', 
                    message=f'🔄 调用RSS监控函数...')
                session.add(log)
                session.commit()
                result = run_bilibili_task(task_id, session)
                print(f"DEBUG: Result = {result}")  # 添加调试
            except Exception as e:
                print(f"DEBUG: Exception = {e}")  # 添加调试
                result = {"error": str(e)}
        else:
            result = {"error": f"不支持的平台: {task.platform}"}
        
        # 记录结果
        new_count = result.get('new_videos', 0) if isinstance(result, dict) else 0
        log = MonitorLog(
            task_id=task_id,
            level='INFO' if 'error' not in result else 'ERROR',
            message=f'任务完成: {new_count} 个新内容'
        )
        session.add(log)
        
        # 更新任务最后运行时间
        task.last_run_at = datetime.now()
        session.commit()
        
    except Exception as e:
        # 记录错误
        try:
            log = MonitorLog(
                task_id=task_id,
                level='ERROR',
                message=f'任务执行失败: {str(e)}'
            )
            session.add(log)
            session.commit()
        except:
            pass
    finally:
        session.close()


def add_task_schedule(task):
    """为任务添加定时调度"""
    if not task.cron_expression or not task.enabled:
        return
    
    # 移除旧调度
    remove_task_schedule(task.id)
    
    # 解析Cron表达式
    try:
        parts = task.cron_expression.split()
        if len(parts) == 5:
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            )
        else:
            trigger = IntervalTrigger(hours=1)
        
        scheduler.add_job(
            run_monitor_task,
            trigger,
            args=[task.id],
            id=f'task_{task.id}',
            name=task.task_name,
            replace_existing=True
        )
        print(f"已添加调度: {task.task_name} - {task.cron_expression}")
    except Exception as e:
        print(f"添加调度失败: {e}")


def remove_task_schedule(task_id):
    """移除任务调度"""
    try:
        scheduler.remove_job(f'task_{task_id}')
    except:
        pass


def start_scheduler():
    """启动调度器"""
    if not scheduler.running:
        session = get_session()
        try:
            from models.monitor.models import MonitorTask
            tasks = session.query(MonitorTask).filter(MonitorTask.enabled == True).all()
            for task in tasks:
                add_task_schedule(task)
        finally:
            session.close()
        
        scheduler.start()
        print("定时任务调度器已启动")


def stop_scheduler():
    """停止调度器"""
    if scheduler.running:
        scheduler.shutdown()
        print("定时任务调度器已停止")


def init_scheduler(app):
    """初始化调度器"""
    start_scheduler()
