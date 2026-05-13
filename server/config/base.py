import os

# =============================================================================
# BUSINESS LOGIC SETTINGS
# =============================================================================

DOMAIN = os.environ.get("DOMAIN", "155.117.46.249")

# Cockfight manager flags (optional)
IS_CF_AUTO_ENABLE = os.environ.get("IS_CF_AUTO_ENABLE", "true").lower() == "true"
IS_CF_MANUAL_STREAM__ENABLE = os.environ.get("IS_CF_MANUAL_STREAM__ENABLE", "true").lower() == "true"
