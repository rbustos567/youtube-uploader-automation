#!/usr/bin/env python3
"""
Jenkins Automation Notification Bridge
Author: DevOps Engineering
Description: Dispatches secure SMTP emails via Google STARTTLS (Port 587).
             Bypasses Jenkins JVM Mail restrictions using native socket layers.
"""

import argparse
import smtplib
import sys
from email.mime.text import MIMEText


def main():
    # Configure argument parser for decoupled configuration management
    parser = argparse.ArgumentParser(
        description="Secure SMTP Email Dispatcher for Jenkins Pipelines"
    )
    parser.add_argument(
        "--to_email", required=True, help="Recipient and sender email address"
    )
    parser.add_argument(
        "--subject", required=True, help="Email header subject line"
    )
    parser.add_argument(
        "--password",
        required=True,
        help="Google App Password (16-character string)",
    )
    parser.add_argument(
        "--body", required=True, help="Main body content / text summary payload"
    )

    args = parser.parse_args()

    # Build MIME structural payload with UTF-8 character encoding
    msg = MIMEText(args.body, "plain", "utf-8")
    msg["Subject"] = args.subject
    msg["From"] = args.to_email
    msg["To"] = args.to_email

    try:
        print("Connecting to Google SMTP gateway via port 587...")
        server = smtplib.SMTP("smtp.gmail.com", 587)

        print("Upgrading cleartext connection to secure layer via STARTTLS...")
        server.starttls()

        print("Authenticating credentials against upstream SMTP server...")
        server.login(args.to_email, args.password)

        print("Transmitting email payload...")
        server.sendmail(args.to_email, [args.to_email], msg.as_string())

        server.quit()
        print(
            "[SUCCESS] Notification email dispatched cleanly via Python runtime."
        )

    except Exception as error:
        print(
            f"[ERROR] Failed to forward email via SMTP gateway: {error}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()