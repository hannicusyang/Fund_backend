import pymysql
import csv

conn = pymysql.connect(
    host='192.168.31.174',
    port=3306,
    user='root',
    password='yangqi',
    database='fund_db'
)

cursor = conn.cursor()

# 获取所有表
cursor.execute("SHOW TABLES")
tables = [row[0] for row in cursor.fetchall()]

for table in tables:
    print(f"Exporting {table}...")
    cursor.execute(f"SELECT * FROM {table}")

    # 获取列名
    columns = [desc[0] for desc in cursor.description]

    # 写入 CSV
    with open(f"{table}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(cursor.fetchall())

cursor.close()
conn.close()
print("Export complete!")