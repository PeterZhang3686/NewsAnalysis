# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': '',
    'password': '',
    'database': 'news_telegraph',
    'charset': 'utf8mb4'
}

# 通义千问 (DashScope) API 配置
QWEN_API_URL = ""
QWEN_API_KEY = ""  # 在阿里云 DashScope 控制台获取
QWEN_MODEL = "qwen3.7-max"


# ==================== 运行参数配置 ====================

# main.py 总结流程使用的参数
SUMMARIZE_DAYS = 1                      # 总结最近多少天的新闻

# wscn_fetcher.py 使用的参数
FETCH_HOURS = 24                        # 抓取最近多少小时的快讯
DEFAULT_CHANNEL = "global-channel"      # 抓取快讯的频道
DEFAULT_LIMIT = 50                      # 单次请求的快讯条数上限

SEND_EMAIL = True                       # True = 总结完成后发送邮件；False = 仅在控制台打印，不发送邮件

# 旧新闻清理配置
SHOULD_CLEAN_OLD_NEWS = True            # True = 启动时清理过期旧新闻；False = 不清理
DEFAULT_RETENTION_DAYS = 7              # 新闻保留天数，超过此天数的记录会被删除


# 邮件发送配置 (SMTP)
SMTP_HOST = "smtp.qq.com"           # SMTP 服务器，QQ 邮箱示例
SMTP_PORT = 465                     # SSL 端口
SMTP_USER = ""     # 发件人邮箱
SMTP_PASSWORD = ""  # SMTP 授权码（非登录密码）
EMAIL_TO = ""      # 收件人邮箱
EMAIL_SUBJECT = "华尔街见闻快讯摘要"