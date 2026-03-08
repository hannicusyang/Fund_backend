"""
通知服务
"""
import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(config, title, content):
    """发送邮件通知"""
    try:
        smtp_host = config.get('smtp_host', 'smtp.qq.com')
        smtp_port = config.get('smtp_port', 465)
        smtp_user = config.get('smtp_user')
        smtp_password = config.get('smtp_password')
        from_email = config.get('from_email', smtp_user)
        to_email = config.get('to_email')
        
        if not smtp_user or not to_email:
            return {"success": False, "error": "缺少邮箱配置"}
        
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = title
        
        msg.attach(MIMEText(content, 'html', 'utf-8'))
        
        # 根据端口选择SSL或TLS
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        
        server.login(smtp_user, smtp_password)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_feishu(config, title, content):
    """发送飞书Webhook通知"""
    try:
        webhook_url = config.get('webhook_url')
        if not webhook_url:
            return {"success": False, "error": "缺少Webhook URL"}
        
        # 构造飞书消息卡片
        message = {
            "msg_type": "interactive_card",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content[:500]  # 限制长度
                    }
                ]
            }
        }
        
        response = requests.post(webhook_url, json=message, timeout=10)
        result = response.json()
        
        if result.get('code') == 0:
            return {"success": True}
        else:
            return {"success": False, "error": result.get('msg', '发送失败')}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_webhook(config, title, content):
    """发送通用Webhook通知"""
    try:
        webhook_url = config.get('webhook_url')
        if not webhook_url:
            return {"success": False, "error": "缺少Webhook URL"}
        
        payload = {
            "title": title,
            "content": content,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        
        headers = {'Content-Type': 'application/json'}
        if config.get('secret'):
            # TODO: 需要签名验证
            pass
        
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return {"success": True}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_notification(notification_type, config, title, content):
    """统一发送通知"""
    if notification_type == 'email':
        return send_email(config, title, content)
    elif notification_type == 'feishu':
        return send_feishu(config, title, content)
    elif notification_type == 'webhook':
        return send_webhook(config, title, content)
    else:
        return {"success": False, "error": f"未知通知类型: {notification_type}"}


from datetime import datetime
