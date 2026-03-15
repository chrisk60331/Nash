#!/usr/bin/env python3
"""Send a Nash-down alert email via Gmail.

Called by nash-watchdog.sh when consecutive failure threshold is reached.

Usage:
    python scripts/nash-alert.py "<subject>" "<body>"

Required env vars (loaded from .env automatically):
    GMAIL_USER              Gmail address used to send
    GMAIL_APP_PASSWORD      Gmail App Password (not account password)
    ALERT_RECIPIENT_EMAIL   Where to deliver the alert
"""

import os
import sys
from pathlib import Path


from api.services.gmail_sender import SendEmailRequest, send_email


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: nash-alert.py <subject> <body>", file=sys.stderr)
        sys.exit(1)

    subject = sys.argv[1]
    body = sys.argv[2]

    recipient = os.getenv("ALERT_RECIPIENT_EMAIL", "")
    if not recipient:
        print("ERROR: ALERT_RECIPIENT_EMAIL is not set", file=sys.stderr)
        sys.exit(1)

    result = send_email(
        SendEmailRequest(
            to_email=recipient,
            subject=subject,
            body=body,
            from_name="Nash Watchdog",
            plain_text_only=True,
        )
    )

    if result.success:
        print("Alert sent.")
    else:
        print(f"Alert to {recipient}: {subject} GMAIL_APP_PASSWORD: {os.getenv('GMAIL_APP_PASSWORD')}", file=sys.stderr)
        print(f"Alert FAILED: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
