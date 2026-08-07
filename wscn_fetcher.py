from datetime import datetime, timedelta
import re
import time
import requests
import pymysql
import config


url = "https://api-prod.wallstreetcn.com/apiv1/content/lives"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://wallstreetcn.com",
    "Referer": "https://wallstreetcn.com/",
}

def show_news(news_data):
    for news in news_data:
        for key, value in news.items():
            print(f"{key}: {value}")
        print("-" * 50)


def clean_html(html_str):
    """移除 HTML 标签，返回纯文本"""
    if not html_str:
        return ""
    text = re.sub(r"<[^>]+>", "", html_str)
    return re.sub(r"\s+", " ", text).strip()


def fetch_news(now_ts,hours=config.FETCH_HOURS, channel=config.DEFAULT_CHANNEL, limit=config.DEFAULT_LIMIT):
    """根据传入参数抓取快讯"""
    target_ts = now_ts - (hours * 3600)  # 使用参数控制计算截止时间戳

    all_news = []
    cursor = ""

    while True:
        params = {"channel": channel, "limit": limit, "cursor": cursor}

        try:
            res = requests.get(url, headers=HEADERS, params=params).json()
            items = res.get("data", {}).get("items", [])
        except Exception as e:
            print(f"[抓取数据失败] 获取新闻失败: {e}")
            return []

        stop_flag = False
        for item in items:
            display_time = item.get("display_time", 0)

            if display_time < target_ts:
                stop_flag = True
                break
            else:
                news_id = item.get("id")
                display_time_str = datetime.fromtimestamp(
                    display_time
                ).strftime("%Y-%m-%d %H:%M:%S")

                raw_content = item.get("content", "") + item.get(
                    "content_more", ""
                )
                full_content = clean_html(raw_content)

                if not full_content:
                    full_content = item.get("content_text", "").strip()

                all_news.append(
                    {
                        "id": news_id,
                        "display_time": display_time_str,
                        "full_content": full_content,
                    }
                )

        if stop_flag:
            break

        next_cursor = res.get("data", {}).get("next_cursor")
        cursor = next_cursor if next_cursor else items[-1].get("display_time")

        time.sleep(0.5)

    print(f"[抓取数据成功] 成功抓取华尔街见闻快讯（频道: {channel}，近 {hours} 小时，{len(all_news)} 条快讯")
    return all_news


def save_to_mysql(news_list):
    """
    将爬取的新闻列表批量存入 MySQL 数据库
    :param news_list: 包含字典的列表，形如 [{'id': ..., 'display_time': ..., 'full_content': ...}]
    """
    if not news_list:
        print("没有可写入的数据")
        return

    conn = pymysql.connect(**config.DB_CONFIG)

    # 使用 ON DUPLICATE KEY UPDATE，防止重复插入报错，若 ID 相同则更新字段
    sql = """
    INSERT INTO wscn_news_global (id, display_time, full_content)
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE
        display_time = VALUES(display_time),
        full_content = VALUES(full_content);
    """

    # 提取参数元组列表
    data_tuples = [
        (item.get('id'), item.get('display_time'), item.get('full_content'))
        for item in news_list
    ]

    try:
        with conn.cursor() as cursor:
            # 批量执行，效率更高
            cursor.executemany(sql, data_tuples)
        conn.commit()
        print(f"[保存数据成功] 成功保存{len(data_tuples)} 条新闻数据")
    except Exception as e:
        conn.rollback()
        print(f"数据写入 MySQL 失败: {e}")
    finally:
        conn.close()


def clean_old_news(now_ts,retention_days):
    """
    根据 display_time 自动清理早于 retention_days 天的新闻数据
    :param db_connection: pymysql 的数据库连接对象
    :param retention_days: 允许保留的最大天数 (整数)
    """
    # 1. 计算 cutoff_date：当前时间向前倒推 retention_days 天的时间点
    cutoff_datetime = datetime.fromtimestamp(now_ts) - timedelta(days=retention_days)
    # 格式化为 MySQL datetime 接受的字符串格式格式
    cutoff_str = cutoff_datetime.strftime('%Y-%m-%d %H:%M:%S')

    # 2. 构建删除 SQL（针对 wscn_news_global 表的 display_time 字段）
    conn = pymysql.connect(**config.DB_CONFIG)
    sql_delete = "DELETE FROM wscn_news_global WHERE display_time < %s"

    try:
        # 使用游标（cursor）执行 SQL 语句
        with conn.cursor() as cursor:
            affected_rows = cursor.execute(sql_delete, (cutoff_str,))

        # 3. 提交事务，写入更改
        conn.commit()
        print(
            f"[清理数据成功] 已清理 {cutoff_str} 之前的数据，共删除 {affected_rows} 条记录，保留最近 {retention_days} 天新闻。")

    except Exception as e:
        # 异常时进行事务回滚，保证数据库状态安全
        conn.rollback()
        print(f"[清理数据失败] 清理数据库时发生错误: {e}")

    conn.close()
