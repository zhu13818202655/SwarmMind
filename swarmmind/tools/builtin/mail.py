"""Mail tool for sending emails."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any


class MailTool:
    """Tool for sending emails."""

    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        username: str | None = None,
        password: str | None = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        from_addr: str | None = None,
        is_html: bool = False,
    ) -> str:
        """Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            from_addr: Sender email address (optional, uses username if not provided)
            is_html: Whether the body is HTML

        Returns:
            Success or error message
        """
        if not self.username or not self.password:
            return "Error: SMTP credentials not configured"

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = from_addr or self.username
            msg['To'] = to

            # Attach body
            mime_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, mime_type))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            return f"Email sent successfully to {to}"

        except Exception as e:
            return f"Error sending email: {str(e)}"


# Tool function for AgentScope
async def send_mail(
    to: str,
    subject: str,
    body: str,
    from_addr: str | None = None,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
    username: str | None = None,
    password: str | None = None,
) -> str:
    """Send an email.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body
        from_addr: Sender email address (optional)
        smtp_host: SMTP server host
        smtp_port: SMTP server port
        username: SMTP username
        password: SMTP password

    Returns:
        Success or error message
    """
    tool = MailTool(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        username=username,
        password=password,
    )
    return await tool.send(to, subject, body, from_addr)
