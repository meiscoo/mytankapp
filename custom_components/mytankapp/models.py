"""Data models for MyTankApp."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .const import USAGE_WINDOW_DAYS


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime | None:
    text = _text(value)
    if text is None or text.startswith("0001-01-01"):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class MyTankAppAccount:
    """Metadata needed to normalize account data."""

    username: str
    display_name: str | None
    default_units: str
    data_source: str | None

    @property
    def uses_liters(self) -> bool:
        """Return whether the account displays metric volume."""
        return self.default_units.casefold() == "liters"

    @property
    def average_usage_is_volume(self) -> bool:
        """Return whether the web client converts average usage to volume."""
        return (self.data_source or "").strip().casefold() == "itank"


@dataclass(frozen=True)
class MyTankAppTank:
    """Normalized tank status."""

    device_id: str
    user_device_id: str | None
    name: str | None
    description: str | None
    fuel_type: str | None
    tank_size: float | None
    inventory: float | None
    ullage: float | None
    level: float | None
    average_daily_usage: float | None
    last_reported: datetime | None
    temperature: float | None
    base_temperature: float | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> MyTankAppTank | None:
        """Create a tank from an API response object."""
        device_id = _text(data.get("DeviceID"))
        if device_id is None:
            return None

        temperature = _float(data.get("Temp"))
        if temperature is not None and temperature < -40:
            temperature = None
        base_temperature = _float(data.get("BaseTemp"))
        if base_temperature is not None and base_temperature < -40:
            base_temperature = None

        return cls(
            device_id=device_id,
            user_device_id=_text(data.get("UserDeviceID")),
            name=_text(data.get("Name")),
            description=_text(data.get("Description")),
            fuel_type=_text(data.get("FuelType")),
            tank_size=_float(data.get("TankSize")),
            inventory=_float(data.get("Inventory")),
            ullage=_float(data.get("Ullage")),
            level=_float(data.get("LastReportedPercent")),
            average_daily_usage=_float(data.get("AverageDailyUsage")),
            last_reported=_datetime(data.get("LastReported")),
            temperature=temperature,
            base_temperature=base_temperature,
        )

    def days_until(self, level: float) -> int | None:
        """Estimate whole days until a percentage threshold from vendor usage."""
        if (
            self.level is None
            or self.average_daily_usage is None
            or self.average_daily_usage <= 0
            or self.level < level
        ):
            return None
        return int(((self.level - level) / self.average_daily_usage) + 0.5)

    def days_until_with_volume_usage(
        self, level: float, daily_volume_usage: float
    ) -> int | None:
        """Estimate days until a level using calculated volume consumption."""
        if (
            self.level is None
            or self.tank_size is None
            or self.tank_size <= 0
            or daily_volume_usage <= 0
            or self.level < level
        ):
            return None
        usable_volume = self.tank_size * (self.level - level) / 100
        return int((usable_volume / daily_volume_usage) + 0.5)

    @property
    def display_name(self) -> str:
        """Return the best non-empty name for the tank."""
        return self.description or self.name or f"Tank {self.device_id[-4:]}"

    @property
    def is_propane(self) -> bool:
        """Return whether the tank contains propane/LPG."""
        fuel_type = (self.fuel_type or "").casefold()
        return "propane" in fuel_type or fuel_type in {"lp", "lpg", "lp gas"}

    @property
    def average_volume_usage_per_day(self) -> float | None:
        """Convert the API's percent-per-day usage to account volume per day."""
        if (
            self.average_daily_usage is None
            or self.average_daily_usage < 0
            or self.tank_size is None
            or self.tank_size <= 0
        ):
            return None
        return self.tank_size * self.average_daily_usage / 100


@dataclass(frozen=True)
class MyTankAppReading:
    """One timestamped tank history reading."""

    reported_at: datetime
    units: float
    percent: float | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> MyTankAppReading | None:
        """Create a reading from a transaction response object."""
        reported_at = _datetime(data.get("TransDate"))
        units = _float(data.get("Units"))
        if reported_at is None or units is None:
            return None
        return cls(
            reported_at=reported_at,
            units=units,
            percent=_float(data.get("Percent")),
        )


PROPANE_KWH_PER_GALLON = 91_452 / 3_412
LITERS_PER_GALLON = 3.785411784


@dataclass
class MyTankAppConsumption:
    """Persisted cumulative propane consumption for one tank."""

    total_kwh: float = 0.0
    total_liters: float = 0.0
    last_inventory: float | None = None
    last_reported: datetime | None = None
    flow_rate_per_hour: float | None = None
    flow_calculated_at: datetime | None = None
    rolling_usage_per_day: float | None = None
    usage_calculated_at: datetime | None = None
    usage_window_days: float | None = None

    @staticmethod
    def _refill_threshold(tank_size: float | None) -> float:
        """Return the volume increase treated as a delivery rather than noise."""
        return max(2.0, (tank_size or 0) * 0.02)

    def update(self, tank: MyTankAppTank, *, uses_liters: bool) -> bool:
        """Apply a new tank reading and return whether stored data changed."""
        current = tank.inventory
        if current is None:
            return False
        if (
            tank.last_reported is not None
            and self.last_reported is not None
            and tank.last_reported <= self.last_reported
        ):
            return False

        if self.last_inventory is None:
            self.last_inventory = current
            self.last_reported = tank.last_reported
            return True

        previous = self.last_inventory
        refill_threshold = self._refill_threshold(tank.tank_size)
        increase = current - previous

        if increase >= refill_threshold:
            # A delivery starts a new consumption baseline; it is not usage.
            self.last_inventory = current
        elif current < previous:
            consumed = previous - current
            gallons = consumed / LITERS_PER_GALLON if uses_liters else consumed
            self.total_kwh += gallons * PROPANE_KWH_PER_GALLON
            self.total_liters += gallons * LITERS_PER_GALLON
            self.last_inventory = current
        # Ignore small increases as gauge/temperature noise. Keeping the lower
        # baseline prevents that noise from being counted again on the next dip.
        self.last_reported = tank.last_reported
        return True

    def update_flow_rate(
        self,
        readings: list[MyTankAppReading],
        *,
        tank_size: float | None,
    ) -> bool:
        """Calculate average volume/hour from the latest two history readings."""
        if len(readings) < 2:
            return False
        newest, previous = readings[0], readings[1]
        if newest.reported_at <= previous.reported_at:
            return False
        if newest.reported_at == self.flow_calculated_at:
            return False

        elapsed_hours = (
            newest.reported_at - previous.reported_at
        ).total_seconds() / 3600
        consumed = previous.units - newest.units
        refill_threshold = self._refill_threshold(tank_size)

        if consumed > 0:
            self.flow_rate_per_hour = consumed / elapsed_hours
        elif -consumed >= refill_threshold:
            self.flow_rate_per_hour = 0.0
        else:
            # Unchanged or slightly higher readings are treated as zero flow,
            # not negative consumption.
            self.flow_rate_per_hour = 0.0
        self.flow_calculated_at = newest.reported_at
        return True

    def update_from_readings(
        self,
        readings: list[MyTankAppReading],
        *,
        tank_size: float | None,
        uses_liters: bool,
    ) -> bool:
        """Apply unseen history points without backfilling before setup."""
        if not readings:
            return False

        ordered = sorted(readings, key=lambda reading: reading.reported_at)
        if self.last_inventory is None:
            newest = ordered[-1]
            self.last_inventory = newest.units
            self.last_reported = newest.reported_at
            return True

        changed = False
        refill_threshold = self._refill_threshold(tank_size)
        for reading in ordered:
            if (
                self.last_reported is not None
                and reading.reported_at <= self.last_reported
            ):
                continue

            previous = self.last_inventory
            current = reading.units
            if previous is None:
                self.last_inventory = current
            else:
                increase = current - previous
                if increase >= refill_threshold:
                    self.last_inventory = current
                elif current < previous:
                    consumed = previous - current
                    gallons = (
                        consumed / LITERS_PER_GALLON if uses_liters else consumed
                    )
                    self.total_kwh += gallons * PROPANE_KWH_PER_GALLON
                    self.total_liters += gallons * LITERS_PER_GALLON
                    self.last_inventory = current

            self.last_reported = reading.reported_at
            changed = True

        return changed

    def update_rolling_usage(
        self,
        readings: list[MyTankAppReading],
        *,
        tank_size: float | None,
        window_days: int = USAGE_WINDOW_DAYS,
    ) -> bool:
        """Calculate rolling daily usage from timestamped history readings."""
        if len(readings) < 2:
            return False

        newest = max(readings, key=lambda reading: reading.reported_at)
        if newest.reported_at == self.usage_calculated_at:
            return False

        cutoff = newest.reported_at - timedelta(days=window_days)
        window = sorted(
            (reading for reading in readings if reading.reported_at >= cutoff),
            key=lambda reading: reading.reported_at,
        )
        if len(window) < 2:
            return False

        elapsed_days = (
            window[-1].reported_at - window[0].reported_at
        ).total_seconds() / 86400
        if elapsed_days <= 0:
            return False

        refill_threshold = self._refill_threshold(tank_size)
        baseline = window[0].units
        consumed = 0.0
        for reading in window[1:]:
            current = reading.units
            increase = current - baseline
            if increase >= refill_threshold:
                baseline = current
            elif current < baseline:
                consumed += baseline - current
                baseline = current

        self.rolling_usage_per_day = consumed / elapsed_days
        self.usage_window_days = elapsed_days
        self.usage_calculated_at = newest.reported_at
        return True

    def as_dict(self) -> dict[str, Any]:
        """Serialize state for Home Assistant storage."""
        return {
            "total_kwh": self.total_kwh,
            "total_liters": self.total_liters,
            "last_inventory": self.last_inventory,
            "last_reported": (
                self.last_reported.isoformat() if self.last_reported else None
            ),
            "flow_rate_per_hour": self.flow_rate_per_hour,
            "flow_calculated_at": (
                self.flow_calculated_at.isoformat()
                if self.flow_calculated_at
                else None
            ),
            "rolling_usage_per_day": self.rolling_usage_per_day,
            "usage_calculated_at": (
                self.usage_calculated_at.isoformat()
                if self.usage_calculated_at
                else None
            ),
            "usage_window_days": self.usage_window_days,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MyTankAppConsumption:
        """Restore state from Home Assistant storage."""
        total_kwh = _float(data.get("total_kwh")) or 0.0
        total_liters = _float(data.get("total_liters"))
        if total_liters is None:
            # Preserve cumulative usage recorded before the volume sensor existed.
            total_liters = (
                total_kwh / PROPANE_KWH_PER_GALLON * LITERS_PER_GALLON
            )
        return cls(
            total_kwh=total_kwh,
            total_liters=total_liters,
            last_inventory=_float(data.get("last_inventory")),
            last_reported=_datetime(data.get("last_reported")),
            flow_rate_per_hour=_float(data.get("flow_rate_per_hour")),
            flow_calculated_at=_datetime(data.get("flow_calculated_at")),
            rolling_usage_per_day=_float(data.get("rolling_usage_per_day")),
            usage_calculated_at=_datetime(data.get("usage_calculated_at")),
            usage_window_days=_float(data.get("usage_window_days")),
        )
