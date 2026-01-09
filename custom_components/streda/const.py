"""Constants for the streda Lights integration."""

DOMAIN = "streda"
VERSION = "0.2.1"

# Configuration
CONF_REFRESH_TOKEN = "refresh_token"
CONF_LOCATION_ID = "location_id"

# Defaults
FALLBACK_DATA_POLL_INTERVAL = 3600  # 1 hour
ACCESS_TOKEN_VALIDITY_CHECK_INTERVAL = 1800  # 30 minutes

# API Endpoints
CLIENT_ID = "ed1f77db-48fe-4a5e-8853-72929d971604"
TENANT = "stredaprod"
POLICY = "b2c_1_homeowner"

STREDA_B2C_TOKEN_URL = (
    f"https://{TENANT}.b2clogin.com/{TENANT}.onmicrosoft.com/{POLICY}/oauth2/v2.0/token"
)

STREDA_AUTHENTICATION_API_URL = (
    "https://streda-authorization-production.azurewebsites.net"
)

STREDA_DATA_API_URL = "https://streda-admin-production.azurewebsites.net"

STREDA_SIGNALR_NEGOTIATE_URL = (
    f"{STREDA_DATA_API_URL}/realtimehub/negotiate?negotiateVersion=1"
)
STREDA_SIGNALR_HUB_URL = (
    "https://streda-signalr-production.service.signalr.net/client/?hub=realtimehub"
)

POSITION_DESCRIPTIONS = {
    "cm": "Ceiling, center",
    "cn": "Ceiling, entry",
    "cf": "Ceiling, far side",
    "edl": "Entry door left",
    "edr": "Entry door right",
    "lwn": "Leftside wall near",
    "lwm": "Leftside wall mid",
    "lwf": "Leftside wall far",
    "rwn": "Rightside wall near",
    "rwm": "Rightside wall mid",
    "rwf": "Rightside wall far",
    "bwl": "Backside wall left",
    "bwm": "Backside wall mid",
    "bwr": "Backside wall right",
}
