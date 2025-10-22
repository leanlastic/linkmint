from typing import Dict, Any
import os, requests

class EmailProvider:
    def send(self, to: str, subject: str, html: str, text: str | None = None) -> None:
        raise NotImplementedError

class DisabledProvider(EmailProvider):
    def send(self, to: str, subject: str, html: str, text: str | None = None) -> None:
        # No-op
        return

class PostmarkProvider(EmailProvider):
    def __init__(self, api_key: str, sender: str):
        self.api_key = api_key
        self.sender = sender

    def send(self, to: str, subject: str, html: str, text: str | None = None) -> None:
        r = requests.post(
            "https://api.postmarkapp.com/email",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": self.api_key,
            },
            json={
                "From": self.sender,
                "To": to,
                "Subject": subject,
                "HtmlBody": html,
                "TextBody": text or "",
                "MessageStream": "outbound",
            },
            timeout=15,
        )
        r.raise_for_status()

class BrevoProvider(EmailProvider):
    def __init__(self, api_key: str, sender: str):
        self.api_key = api_key
        self.sender = sender

    def send(self, to: str, subject: str, html: str, text: str | None = None) -> None:
        r = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": self.api_key,
                "content-type": "application/json",
            },
            json={
                "sender": {"email": self.sender},
                "to": [{"email": to}],
                "subject": subject,
                "htmlContent": html,
                "textContent": text or "",
            },
            timeout=15,
        )
        r.raise_for_status()

class SendgridProvider(EmailProvider):
    def __init__(self, api_key: str, sender: str):
        self.api_key = api_key
        self.sender = sender

    def send(self, to: str, subject: str, html: str, text: str | None = None) -> None:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{"to": [{"email": to}], "subject": subject}],
                "from": {"email": self.sender},
                "content": [{"type": "text/html", "value": html}],
            },
            timeout=15,
        )
        r.raise_for_status()

def build_provider() -> EmailProvider:
    provider = os.getenv("EMAIL_PROVIDER", "disabled").strip().lower()
    api_key = os.getenv("EMAIL_API_KEY", "")
    sender = os.getenv("EMAIL_FROM", "")
    if provider == "postmark" and api_key and sender:
        return PostmarkProvider(api_key, sender)
    if provider == "brevo" and api_key and sender:
        return BrevoProvider(api_key, sender)
    if provider == "sendgrid" and api_key and sender:
        return SendgridProvider(api_key, sender)
    return DisabledProvider()
