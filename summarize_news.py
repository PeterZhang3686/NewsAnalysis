import pymysql
import requests
import smtplib
import markdown
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

import config


def fetch_news_from_db(now_ts, days=config.SUMMARIZE_DAYS):
    """从 MySQL 提取最近 days 天内的新闻"""
    conn = pymysql.connect(**config.DB_CONFIG)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT display_time, full_content
                FROM wscn_news_global
                WHERE display_time >= %s
                ORDER BY display_time ASC
            """
            cutoff = datetime.fromtimestamp(now_ts) - timedelta(days=days)
            cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(sql, (cutoff_str,))
            news_list = cursor.fetchall()
            return news_list
    finally:
        conn.close()


def summarize_with_qwen(news_list, days):
    """将新闻发送给通义千问 API 进行总结"""
    if not news_list:
        print(f"过去 {days} 天内没有新闻数据。")
        return None

    # 格式化新闻列表
    formatted_news = []
    for idx, item in enumerate(news_list, 1):
        time_str = (
            item['display_time'].strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(item['display_time'], datetime)
            else str(item['display_time'])
        )
        formatted_news.append(f"[{idx}] 时间：{time_str}\n内容：{item['full_content']}")

    combined_text = "\n\n".join(formatted_news)

    prompt = f"""以下是过去 {days} 天内收集到的全球金融市场新闻快讯（类似华尔街见闻电报），共 {len(news_list)} 条。

请阅读并深度分析上述新闻内容，按照以下结构输出分析报告：

1. **核心叙事与情绪概览**
   * **一句话核心叙事**：用一句精炼的话概括过去 {days} 天主导市场的最强逻辑。
   * **市场情绪**：用几个关键词描述当前市场情绪（如：恐慌、贪婪、避险、观望、滞胀交易等）。

2. **资产类别影响分析**
   请逐条分析以下资产类别的**潜在影响方向**（利多/利空/中性）及**核心驱动逻辑**。请务必结合新闻中的具体事件（如某公司财报、某项数据发布、某地缘冲突）进行归因。
   * **🇨🇳 A股**：关注政策面、外资流向、特定板块（如科技、新能源）的映射。
   * **🇺🇸 美股**：关注科技巨头（Mag 7）表现、美联储政策预期、经济衰退风险。
   * **📉 债券**：关注美债收益率走势、信用利差、各国央行动态。
   * **💱 汇率**：重点关注美元指数（DXY）及主要非美货币（人民币、日元、欧元）的波动逻辑。
   * **🥇 黄金**：关注实际利率变化、避险买盘及央行购金需求。
   * **🛢️ 原油**：关注供需平衡表变化、地缘政治风险溢价及库存数据。

【分析约束】
* **逻辑严密**：分析必须基于提供的新闻事实，不要凭空猜测。
* **专业简练**：使用金融专业术语（如：避险属性、流动性溢价、鹰派/鸽派），但解释要通俗易懂。
* **时效性**：默认当前时间为新闻发生的“当下”，进行即时点评。

--- 新闻原文 ---
{combined_text}
"""

    headers = {
        "Authorization": f"Bearer {config.QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": config.QWEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一位拥有20年经验的华尔街资深宏观策略分析师，擅长通过碎片化的电报新闻（Flash News）捕捉市场核心逻辑，并快速判断各类资产的潜在走势。"
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    print(f"[模型总结中] 正在调用 {config.QWEN_MODEL} 进行总结...")
    response = requests.post(config.QWEN_API_URL, headers=headers, json=payload, timeout=600)

    if response.status_code == 200:
        summary = response.json()['choices'][0]['message']['content']
        return summary
    else:
        print(f"API 请求失败，状态码: {response.status_code}")
        print(f"响应详情: {response.text}")
        return None


def send_email(subject, body):
    """通过 SMTP 发送邮件"""
    msg = MIMEMultipart('alternative')
    msg['From'] = config.SMTP_USER
    msg['To'] = config.EMAIL_TO
    msg['Subject'] = subject

    # 把模型返回的 Markdown 转换成 HTML，标题/加粗/列表才能正常渲染
    # extra 扩展支持表格、围栏代码块等语法
    html_content = markdown.markdown(body, extensions=['extra'])

    html_body = f"""
    <html><body>
    <div style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; max-width: 860px; margin: 0 auto;">
    {html_content}
    <hr>
    <p style="color: #888; font-size: 12px;">此邮件由 NewsAnalysis 自动生成，时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    </body></html>
    """
    # 先附纯文本版本（不支持 HTML 的客户端兜底），再附 HTML 版本
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_USER, config.EMAIL_TO, msg.as_string())
        print(f"[模型总结结束] 邮件发送成功 → {config.EMAIL_TO}")
    except Exception as e:
        print(f"邮件发送失败: {e}")


