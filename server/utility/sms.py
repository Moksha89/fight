"""
SMS Gateway — Full Provider System
====================================
Supports MSG91, Twilio, and None/disabled mode.

Configuration priority:
1. Admin DB config (SmsProviderSetting) if enabled
2. Environment variable fallback
3. None / disabled

Environment variables (fallback when admin config not set):
  SMS_PROVIDER            "none" | "msg91" | "twilio"
  SMS_DEFAULT_COUNTRY_CODE  default "91"
  MSG91_AUTH_KEY
  MSG91_TEMPLATE_ID
  MSG91_SENDER_ID
  MSG91_ROUTE
  MSG91_ENTITY_ID
  MSG91_BASE_URL
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_FROM_NUMBER
  TWILIO_MESSAGING_SERVICE_SID
"""

import logging
import os
import re

import requests as http_requests

logger = logging.getLogger("kokoroko.sms")


# ─── Mobile number normalisation ─────────────────────────────────────────────

def normalize_mobile(mobile, country_code="91", fmt="e164"):
    """
    Normalise a mobile number.

    Accepts:  9876543210, 919876543210, +919876543210, 091-9876543210
    Returns:
        fmt="e164"   → "+919876543210"  (Twilio style)
        fmt="plain"  → "919876543210"   (MSG91 style)
        fmt="local"  → "9876543210"     (10-digit local)
    """
    digits = re.sub(r"[^0-9]", "", mobile)

    if digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == 10:
        digits = country_code + digits
    elif digits.startswith(country_code) and len(digits) == len(country_code) + 10:
        pass
    elif len(digits) > 10:
        digits = country_code + digits[-10:]

    if fmt == "e164":
        return "+" + digits
    elif fmt == "local":
        return digits[-10:]
    return digits


# ─── Config loader ────────────────────────────────────────────────────────────

def _get_sms_config():
    """
    Load SMS configuration.
    Priority: DB admin config > environment variables.
    Returns a dict with all needed settings.
    """
    config = {
        "provider": os.environ.get("SMS_PROVIDER", "none").lower(),
        "is_enabled": os.environ.get("SMS_PROVIDER", "none").lower() != "none",
        "country_code": os.environ.get("SMS_DEFAULT_COUNTRY_CODE", "91"),
        "msg91_auth_key": os.environ.get("MSG91_AUTH_KEY", ""),
        "msg91_template_id": os.environ.get("MSG91_TEMPLATE_ID", ""),
        "msg91_sender_id": os.environ.get("MSG91_SENDER_ID", ""),
        "msg91_route": os.environ.get("MSG91_ROUTE", ""),
        "msg91_entity_id": os.environ.get("MSG91_ENTITY_ID", ""),
        "msg91_base_url": os.environ.get("MSG91_BASE_URL", "https://control.msg91.com/api/v5/otp"),
        "twilio_account_sid": os.environ.get("TWILIO_ACCOUNT_SID", ""),
        "twilio_auth_token": os.environ.get("TWILIO_AUTH_TOKEN", ""),
        "twilio_from_number": os.environ.get("TWILIO_FROM_NUMBER", ""),
        "twilio_messaging_service_sid": os.environ.get("TWILIO_MESSAGING_SERVICE_SID", ""),
        "otp_message_template": "Your KOKOROKO OTP is {otp}. It is valid for 5 minutes. Do not share it with anyone.",
        "source": "env",
    }

    try:
        from base.models import SmsProviderSetting
        db_config = SmsProviderSetting.objects.first()
        if db_config:
            config["provider"] = db_config.provider
            config["is_enabled"] = db_config.is_enabled
            config["country_code"] = db_config.default_country_code or config["country_code"]
            if db_config.otp_message_template:
                config["otp_message_template"] = db_config.otp_message_template

            if db_config.provider == "msg91":
                db_key = db_config.get_msg91_auth_key()
                if db_key:
                    config["msg91_auth_key"] = db_key
                if db_config.msg91_template_id:
                    config["msg91_template_id"] = db_config.msg91_template_id
                if db_config.msg91_sender_id:
                    config["msg91_sender_id"] = db_config.msg91_sender_id
                if db_config.msg91_route:
                    config["msg91_route"] = db_config.msg91_route
                if db_config.msg91_entity_id:
                    config["msg91_entity_id"] = db_config.msg91_entity_id
                if db_config.msg91_base_url:
                    config["msg91_base_url"] = db_config.msg91_base_url

            elif db_config.provider == "twilio":
                db_sid = db_config.get_twilio_account_sid()
                db_token = db_config.get_twilio_auth_token()
                if db_sid:
                    config["twilio_account_sid"] = db_sid
                if db_token:
                    config["twilio_auth_token"] = db_token
                if db_config.twilio_from_number:
                    config["twilio_from_number"] = db_config.twilio_from_number
                if db_config.twilio_messaging_service_sid:
                    config["twilio_messaging_service_sid"] = db_config.twilio_messaging_service_sid

            config["source"] = "db"
    except Exception:
        pass

    return config


# ─── Public API ───────────────────────────────────────────────────────────────

def send_otp_sms(mobile, otp):
    """
    Send an OTP to *mobile*.
    Returns (success: bool, error_message: str or None).
    """
    config = _get_sms_config()
    provider = config["provider"]

    if not config["is_enabled"] or provider == "none":
        logger.warning(
            "SMS disabled (provider=%s, enabled=%s) — OTP for %s stored but NOT sent.",
            provider, config["is_enabled"], _mask(mobile),
        )
        return False, "SMS delivery is not configured."

    if provider == "msg91":
        return _send_msg91(mobile, otp, config)
    elif provider == "twilio":
        return _send_twilio(mobile, otp, config)
    else:
        logger.error("Unknown SMS provider: %s", provider)
        return False, f"Unknown provider: {provider}"


def send_test_otp(mobile, provider_override=None):
    """
    Send a test OTP and record the result in SmsProviderSetting.
    Returns (success, otp_value, error_message).
    """
    import random
    from django.utils import timezone

    test_otp = str(random.randint(100000, 999999))
    config = _get_sms_config()

    if provider_override and provider_override != "none":
        config["provider"] = provider_override
        config["is_enabled"] = True

    provider = config["provider"]
    if not config["is_enabled"] or provider == "none":
        return False, test_otp, "SMS is disabled. Select a provider and enable SMS first."

    if provider == "msg91":
        success, err = _send_msg91(mobile, test_otp, config)
    elif provider == "twilio":
        success, err = _send_twilio(mobile, test_otp, config)
    else:
        success, err = False, f"Unknown provider: {provider}"

    try:
        from base.models import SmsProviderSetting
        db_config = SmsProviderSetting.get_config()
        db_config.last_test_status = "success" if success else "failed"
        db_config.last_test_error = err or ""
        db_config.last_test_at = timezone.now()
        db_config.last_test_mobile = _mask(mobile)
        db_config.save(update_fields=[
            "last_test_status", "last_test_error",
            "last_test_at", "last_test_mobile",
        ])
    except Exception as exc:
        logger.warning("Could not update test status: %s", exc)

    return success, test_otp, err


# ─── MSG91 ────────────────────────────────────────────────────────────────────

def _send_msg91(mobile, otp, config):
    auth_key = config.get("msg91_auth_key", "")
    template_id = config.get("msg91_template_id", "")
    base_url = config.get("msg91_base_url", "https://control.msg91.com/api/v5/otp")

    if not auth_key:
        return False, "MSG91 auth key is not configured."
    if not template_id:
        return False, "MSG91 template ID is not configured."

    country_code = config.get("country_code", "91")
    normalized = normalize_mobile(mobile, country_code, fmt="plain")

    payload = {
        "template_id": template_id,
        "mobile": normalized,
        "otp": otp,
    }
    if config.get("msg91_sender_id"):
        payload["sender"] = config["msg91_sender_id"]
    if config.get("msg91_entity_id"):
        payload["DLT_TE_ID"] = config["msg91_entity_id"]

    headers = {"authkey": auth_key, "Content-Type": "application/json"}

    try:
        resp = http_requests.post(base_url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        resp_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        msg_type = resp_data.get("type", "")
        if msg_type == "error":
            err_msg = resp_data.get("message", "MSG91 returned error")
            logger.error("MSG91 error for %s: %s", _mask(mobile), err_msg)
            return False, err_msg
        logger.info("MSG91 OTP sent to %s", _mask(mobile))
        return True, None
    except http_requests.exceptions.HTTPError as exc:
        err = f"MSG91 HTTP {exc.response.status_code}"
        try:
            err += f": {exc.response.text[:200]}"
        except Exception:
            pass
        logger.error("MSG91 send failed for %s: %s", _mask(mobile), err)
        return False, err
    except Exception as exc:
        logger.error("MSG91 send failed for %s: %s", _mask(mobile), exc)
        return False, str(exc)


# ─── Twilio ───────────────────────────────────────────────────────────────────

def _send_twilio(mobile, otp, config):
    sid = config.get("twilio_account_sid", "")
    token = config.get("twilio_auth_token", "")
    from_number = config.get("twilio_from_number", "")
    messaging_sid = config.get("twilio_messaging_service_sid", "")

    if not sid or not token:
        return False, "Twilio Account SID and Auth Token are required."
    if not from_number and not messaging_sid:
        return False, "Twilio requires either a From Number or Messaging Service SID."

    country_code = config.get("country_code", "91")
    to_number = normalize_mobile(mobile, country_code, fmt="e164")

    message_body = config.get("otp_message_template", "Your OTP is {otp}").format(otp=otp)

    data = {"To": to_number, "Body": message_body}
    if messaging_sid:
        data["MessagingServiceSid"] = messaging_sid
    else:
        data["From"] = from_number

    try:
        resp = http_requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data=data,
            auth=(sid, token),
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Twilio OTP sent to %s", _mask(mobile))
        return True, None
    except http_requests.exceptions.HTTPError as exc:
        err = f"Twilio HTTP {exc.response.status_code}"
        try:
            err += f": {exc.response.json().get('message', '')[:200]}"
        except Exception:
            pass
        logger.error("Twilio send failed for %s: %s", _mask(mobile), err)
        return False, err
    except Exception as exc:
        logger.error("Twilio send failed for %s: %s", _mask(mobile), exc)
        return False, str(exc)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mask(mobile):
    if len(mobile) > 4:
        return mobile[:2] + "****" + mobile[-2:]
    return "****"
