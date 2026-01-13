import re
from datetime import datetime

def parse_quarter_from_text(quarter_text: str):
    """
    将 "2024年1季度" 转为 ("2024Q1", "2024-03-31")
    """
    if not quarter_text:
        return None, None

    match = re.search(r'(\d{4})年(\d)季度', quarter_text)
    if not match:
        return None, None

    year, q = match.groups()
    year = int(year)
    q = int(q)

    # 季度末日期
    quarter_end_map = {
        1: f"{year}-03-31",
        2: f"{year}-06-30",
        3: f"{year}-09-30",
        4: f"{year}-12-31"
    }
    report_date = quarter_end_map.get(q)
    quarter_std = f"{year}Q{q}"
    return quarter_std, report_date