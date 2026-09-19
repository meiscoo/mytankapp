# MyTankApp for Home Assistant

An unofficial, read-only Home Assistant custom integration for tanks visible at [MyTankApp](https://www.mytankapp.com).

## Entities

Each tank becomes a Home Assistant device with sensors for:

- Level
- Inventory and ullage
- Capacity
- Average daily usage
- Last report time
- Last successful integration sync time
- Temperature and base temperature
- Estimated days to 30%, 15%, and empty
- Cumulative propane energy consumed in kWh for the Energy Dashboard
- Cumulative propane volume consumed in liters for the Energy Dashboard gas chart
- Configurable low-level problem state

The estimates match the website's basic calculation and are unavailable when usage is zero, negative, or the tank is already below the target.

The cumulative consumption sensors count decreases in reported inventory, ignore deliveries, filter small upward gauge fluctuations, and persist across Home Assistant restarts. Add **Propane consumed** under **Settings → Dashboards → Energy → Gas consumption** for the gas chart. Keep **Propane energy consumed** on summary views where a kWh equivalent is useful. Existing tank history is not backfilled, but upgrades preserve the consumption accumulated by earlier versions.

## Installation

### HACS custom repository

1. Add this repository to HACS as an **Integration** custom repository.
2. Install **MyTankApp**.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and select **MyTankApp**.

### Manual

Copy `custom_components/mytankapp` into your Home Assistant `config/custom_components` directory and restart Home Assistant.

## Configuration

Enter the username and password used at `mytankapp.com`. The password is retained by Home Assistant because the website provides no refresh-token flow and the integration must log in again after restarts or expired sessions.

The default poll interval is 6 hours. Options allow 1–24 hours and a 1–99% low-level threshold. Existing installations are migrated to the six-hour interval when upgrading to version 0.5.0. Because this is a private, undocumented API with no published quota, the default interval is intentionally conservative.

All failed automatic login responses use a 15-minute cooldown; calls made during the cooldown do not send another login request. This accommodates intermittent login failures from MyTankApp without rapidly retrying. Credentials submitted interactively in Home Assistant setup or reauthentication are still validated immediately, and an invalid response is shown to the user. Once automatic access recovers, normal six-hour polling resumes.

## Safety and limitations

- The integration does not order fuel, request service, modify alerts, or change account data.
- MyTankApp does not publish this API, so upstream changes can break the integration.
- Tank reading cadence is controlled by the physical monitor and supplier; frequent polling will not make the transmitter report more often.
- Historical graph endpoints are intentionally omitted. Home Assistant Recorder stores the sensor history locally.

## Support data

Home Assistant diagnostics redact credentials and tank identifiers. Before sharing logs, still check them for personal information.
