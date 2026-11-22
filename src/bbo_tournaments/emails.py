"""Send and or save emails."""

import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv
from psiutils.constants import Status
from psiutils.errors import ErrorMsg

from bbo_tournaments import logger

load_dotenv()


def send() -> str:
    """Create an email message."""
    subject = "Testing"
    body = "Testing email functionality"
    recipients = ["jeffwatkins2000@gmail.com"]
    send_emails(recipients, subject, body)


def send_emails(
    recipients: list[str], subject: str, body: str
) -> int | ErrorMsg:
    """Send emails to the directors."""
    logger.info("Sending emails...")
    emails_sent = 0
    if not (
        os.getenv("EMAIL_SENDER")
        and os.getenv("EMAIL_KEY")
        and os.getenv("SMTP_PORT")
        and os.getenv("SMTP_SERVER")
    ):
        logger.warning("Email configuration is incomplete.")
        return Status.WARNING
    for recipient in recipients:
        logger.info(f"Sending email to {recipient}")
        response = _create_email(subject, body, recipient)
        if isinstance(response, ErrorMsg):
            return response
        emails_sent += 1
    return Status.SUCCESS


def _create_email(subject: str, body: str, recipient: str) -> str:
    try:
        _send_email(subject, body, recipient)
    except smtplib.SMTPAuthenticationError:
        logger.error("Email authentication error.")
        return Status.ERROR
    except TypeError:
        logger.error("Email setup error.")
        return Status.ERROR
    return Status.SUCCESS


def _send_email(subject: str, body: str, recipient: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("email_sender")
    msg["To"] = recipient
    msg.set_content(body)
    # recipient = os.getenv("EMAIL_SENDER")

    with smtplib.SMTP_SSL(
        os.getenv("SMTP_SERVER"), os.getenv("SMTP_PORT")
    ) as smtp:
        smtp.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_KEY"))
        smtp.send_message(msg)
    logger.info(f"Email sent to {recipient}")
