from __future__ import annotations

# 邮件通知服务（企微消息降级通道）
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from pms.configs.settings import settings


def send_email(
    to_emails: list[str],
    subject: str,
    content: str,
    content_type: str = "plain",
) -> bool:
    """发送邮件。

    Args:
        to_emails: 收件人邮箱列表
        subject: 邮件主题
        content: 邮件内容
        content_type: "plain" 或 "html"

    Returns:
        是否发送成功
    """
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP 配置不完整，邮件未发送: {}", subject)
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.smtp_from_email or settings.smtp_user
        msg["To"] = ", ".join(to_emails)
        msg["Subject"] = subject

        if content_type == "html":
            msg.attach(MIMEText(content, "html", "utf-8"))
        else:
            msg.attach(MIMEText(content, "plain", "utf-8"))

        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from_email or settings.smtp_user, to_emails, msg.as_string())
        server.quit()
        logger.info("邮件发送成功: {} -> {}", subject, to_emails)
        return True
    except Exception as exc:
        logger.warning("邮件发送失败: {} -> {}, error={}", subject, to_emails, exc)
        return False
