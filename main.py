"""
NewsAnalysis 程序入口

完整流程：抓取华尔街见闻新闻 → 存入 MySQL → 调用通义千问 AI 总结 → 发送邮件
"""
from datetime import datetime
import time
import config
import wscn_fetcher
from summarize_news import fetch_news_from_db, summarize_with_qwen, send_email


def main():
    """
    主流程：抓取华尔街见闻新闻 → 存入数据库 → AI 总结 → 发送邮件

    流程分为两个阶段：
    1. 数据采集阶段：从华尔街见闻抓取最新新闻，持久化到 MySQL 数据库
    2. 分析推送阶段：从数据库提取新闻，调用通义千问进行深度分析，可选发送邮件
    """
    now_time = int(time.time())
    # ========== 阶段一：数据采集与存储 ==========

    # 从华尔街见闻 API 抓取最新新闻快讯
    news_data = wscn_fetcher.fetch_news(now_ts=now_time)

    # 将抓取到的新闻数据持久化到 MySQL 数据库
    # 注意：即使新闻已存在，save_to_mysql 内部会处理去重逻辑
    wscn_fetcher.save_to_mysql(news_data)

    # 清理过期新闻数据，防止数据库无限增长
    # 仅在配置开启时执行，默认保留 DEFAULT_RETENTION_DAYS 天的数据
    if config.SHOULD_CLEAN_OLD_NEWS:
        wscn_fetcher.clean_old_news(now_ts=now_time, retention_days=config.DEFAULT_RETENTION_DAYS)

    # ========== 阶段二：AI 分析与推送 ==========

    # 从数据库提取指定时间范围内的新闻用于总结
    # SUMMARIZE_DAYS 控制分析的时间窗口（如 1 表示过去 1 天的新闻）
    days = config.SUMMARIZE_DAYS
    # print(f"正在从数据库提取过去 {days} 天的新闻...")
    news_list = fetch_news_from_db(now_ts=now_time, days=days)
    # print(f"提取到 {len(news_list)} 条新闻")

    # 如果时间窗口内没有新闻，提前退出避免无意义的 API 调用
    if not news_list:
        print("没有新闻数据，退出。")
        return

    # 调用通义千问 API 对新闻进行深度分析
    # API 会以华尔街资深宏观策略分析师的角色，输出专业的市场分析报告
    summary = summarize_with_qwen(news_list, days=days)
    if not summary:
        print("AI 总结失败，退出。")
        return
    # header = f"=== 华尔街见闻快讯摘要（过去 {days} 天）==="
    # print(f"\n{header}")
    # print(summary)

    # 通过邮件推送分析报告（可选）
    # SEND_EMAIL=False 时可仅运行分析流程而不发送邮件，适合测试场景
    if config.SEND_EMAIL:
        email_subject = f"{config.EMAIL_SUBJECT} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        send_email(email_subject, summary)
    else:
        print("\n（已跳过邮件发送）")


if __name__ == "__main__":
    main()
