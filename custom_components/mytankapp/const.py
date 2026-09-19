"""Constants for the MyTankApp integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "mytankapp"
PLATFORMS: Final = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_LOW_LEVEL: Final = "low_level"

DEFAULT_SCAN_INTERVAL: Final = 360
LOGIN_RETRY_INTERVAL: Final = 15
DEFAULT_LOW_LEVEL: Final = 20
MIN_SCAN_INTERVAL: Final = 60
MAX_SCAN_INTERVAL: Final = 1440

BASE_URL: Final = "https://www.mytankapp.com"
