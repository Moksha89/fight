"""
SMS Gateway Abstraction
========================
Provides a single entry point — ``send_otp_sms(mobile, otp)`` — to deliver
OTP codes via whichever SMS provider is configured.

Environment variables
---------------------
SMS_PROVIDER    Provider name: "none" | "msg91" | "twilio" (default: "none")
SMS_MSG91_KEY   MSG91 auth key (required when SMS_PROVIDER=msg91)
SMS_MSG91_TEMPLATE  MSG91 template ID (required when SMS_PROVIDER=msg91)
SMS_TWILIO_SID  Twilio Account SID (required when SMS_PROVIDER=twilio)
SMS_TWILIO_TOKEN Twilio Auth Token (required when SMS_PROVIDER=twilio)
SMS_TWILIO_FROM  Twilio sender number (required when SMS_PROVIDER=twilio)

When SMS_PROVIDER is "none" (the default), OTPs are **not** sent.  A warning
is logged so operators notice the gap.  The OTP is still stored in the DB
for retrieval by testers via the Django admin / shell.
"""

import logging
import os

import requests

logger = logging.getLogger("kokoroko.security")

_PROVIDER = os.environ.get("SMS_PROVIDER", "none").lower()


def send_otp_sms(mobile: str, otp: str) -> bool:
    """Send an OTP to *mobile*.  Returns ``True`` on success."""
    if _PROVIDER == "msg91":
        return _send_msg91(mobile, otp)
    elif _PROVIDER == "twilio":
        return _send_twilio(mobile, otp)
    else:
        logger.warning(
            "SMS_PROVIDER not configured — OTP for %s stored but NOT sent. "
            "Set SMS_PROVIDER env var to enable delivery.",
            mobile[:4] + "****",
        )
        return False


# ─── MSG91 ───────────────────────────────────────────────────────────────────

def _send_msg91(mobile: str, otp: str) -> bool:
    auth_key = os.environ.get("SMS_MSG91_KEY", "")
    template_id = os.environ.get("SMS_MSG91_TEMPLATE", "")
    if not auth_key or not template_id:
        logger.error("MSG91 credentials missing (SMS_MSG91_KEY / SMS_MSG91_TEMPLATE)")
        return False
    try:
        resp = requests.post(
            "https://control.msg91.com/api/v5/otp",
            json={
                "template_id": template_id,
                "mobile": mobile,
                "otp": otp,
            },
            headers={"authkey": auth_key},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("MSG91 OTP sent to %s", mobile[:4] + "****")
        return True
    except Exception as exc:
        logger.error("MSG91 send failed for %s: %s", mobile[:4] + "****", exc)
        return False


# ─── Twilio ──────────────────────────────────────────────────────────────────

def _send_twilio(mobile: str, otp: str) -> bool:
    sid = os.environ.get("SMS_TWILIO_SID", "")
    token = os.environ.get("SMS_TWILIO_TOKEN", "")
    from_number = os.environ.get("SMS_TWILIO_FROM", "")
    if not sid or not token or not from_number:
        logger.error("Twilio credentials missing (SMS_TWILIO_SID / TOKEN / FROM)")
        return False
    try:
        resp = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={
                "To": mobile,
                "From": from_number,
                "Body": f"Your OTP is {otp}. Valid for 5 minutes.",
            },
            auth=(sid, token),
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Twilio OTP sent to %s", mobile[:4] + "****")
        return True
    except Exception as exc:
        logger.error("Twilio send failed for %s: %s", mobile[:4] + "****", exc)
        return False
