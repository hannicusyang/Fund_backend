# ====== MySQL 配置 ======
MYSQL_CONFIG = {
    'user': 'root',
    'password': 'yangqi',
    'host': '192.168.31.174',
    'port': 3306,
    'database': 'fund_db'
}

DB_URL = f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@" \
         f"{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}?charset=utf8mb4"
