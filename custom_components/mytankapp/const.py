"""Constants for the MyTankApp integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "mytankapp"
PLATFORMS: Final = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_LOW_LEVEL: Final = "low_level"
CONF_LEVEL_OFFSET: Final = "level_offset"

DEFAULT_SCAN_INTERVAL: Final = 720
LOGIN_RETRY_INTERVAL: Final = 720
DEFAULT_LOW_LEVEL: Final = 20
DEFAULT_LEVEL_OFFSET: Final = 0.0
MIN_SCAN_INTERVAL: Final = 60
MAX_SCAN_INTERVAL: Final = 1440
MIN_LEVEL_OFFSET: Final = -50.0
MAX_LEVEL_OFFSET: Final = 50.0
USAGE_WINDOW_DAYS: Final = 7

BASE_URL: Final = "https://www.mytankapp.com"
