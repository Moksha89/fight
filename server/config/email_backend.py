"""
Custom SMTP email backend that works with Python 3.13+.

Python 3.13 enforces stricter SSL verification (Basic Constraints must be critical).
Brevo's SMTP server cert can trigger: CERTIFICATE_VERIFY_FAILED ... Basic Constraints of CA cert not marked critical.
This backend uses an SSL context with VERIFY_X509_STRICT disabled so SMTP TLS works.
"""
import ssl

from django.core.mail.backends.smtp import EmailBackend
from django.utils.functional import cached_property


class BrevoSMTPBackend(EmailBackend):
    """SMTP backend that relaxes Python 3.13 strict SSL verification for Brevo."""

    @cached_property
    def ssl_context(self):
        context = ssl.create_default_context()
        # Python 3.13+ only: avoid "Basic Constraints of CA cert not marked critical" failure
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return context
