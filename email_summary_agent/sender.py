"""
SMTP email sender.

Delivers the summary digest to the configured recipient.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_summary(smtp_config, recipient, subject, plain_text, html_text):
    """
    Send the summary email via SMTP.

    Args:
        smtp_config: dict with server, port, email, password, use_tls keys
        recipient: email address to deliver the summary to
        subject: email subject line
        plain_text: plain-text version of the summary
        html_text: HTML version of the summary
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_config["email"]
    msg["To"] = recipient
    msg["Subject"] = subject

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_text, "html"))

    use_tls = smtp_config.get("use_tls", True)
    port = smtp_config["port"]

    if use_tls:
        server = smtplib.SMTP(smtp_config["server"], port)
        server.ehlo()
        server.starttls()
        server.ehlo()
    else:
        server = smtplib.SMTP_SSL(smtp_config["server"], port)

    server.login(smtp_config["email"], smtp_config["password"])
    server.sendmail(smtp_config["email"], recipient, msg.as_string())
    server.quit()
    print(f"  Summary sent to {recipient}")
