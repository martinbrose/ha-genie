# HA Genie 🧞‍♂️

**Artificial Intelligence for your Home Assistant**

HA Genie aggregates your home's sensor data (Temperature, Energy, Air Quality) and uses Google's Gemini API to provide weekly health and efficiency reports. It benchmarks your usage against UK averages (electricity/gas) and checks for health risks (mould/humidity, VOCs).

> [!WARNING]
> **Disclaimer**: This component sends data to Google's Gemini API. By using this integration, you agree to transmit your home's aggregated sensor data to Google.

## Features

-   **Weekly Reports**: Automated analysis of the last 7 days.
-   **Privacy Focused**: Only sends aggregated metadata (averages/totals) to Google. Raw sensor history stays local.
-   **UK Benchmarking**: Compares energy usage against typical UK households (e.g. Electricity ~2,700 kWh/yr).
-   **3 Sensors**:
    -   `sensor.genie_summary`: Overall status and detailed attributes.
    -   `sensor.genie_insights`: Positive trends detected.
    -   `sensor.genie_alerts`: Issues needing attention (e.g., high humidity).

## Installation

### Option 1: HACS (Recommended)

1.  Ensure [HACS](https://hacs.xyz/) is installed.
2.  In the HACS panel, go to **Integrations**.
3.  Click the menu (three dots) in the top right -> **Custom repositories**.
4.  Add the URL of this repository: `https://github.com/USERNAME/ha_genie`
    -   Category: `Integration`
5.  Click **Add**, then search for "HA Genie" and click **Install**.
6.  Restart Home Assistant.

### Option 2: Manual Installation

1.  Download the `ha_genie` zip from Releases.
2.  Copy the `custom_components/ha_genie` folder to your Home Assistant `config/custom_components/` directory.
3.  Restart Home Assistant.

## Configuration

1.  Go to **Settings** > **Devices & Services**.
2.  Click **Add Integration** and search for "HA Genie".
3.  **API Key**: Enter your Google Gemini API Key.
    -   *Get a key here*: [Google AI Studio](https://makersuite.google.com/app/apikey).
4.  **House Details**:
    -   Bedrooms: Used to estimate typical usage.
    -   Size (sqm): Used to contextuallise heating loads.
5.  **Entities**: Select the sensors you wish to include in the analysis.

> [!NOTE]
> You can change these settings later by clicking **Configure** on the integration card.

## Costs & Limits

This integration uses the Google Gemini API.

-   **Free Tier**: Currently, Google offers a free tier for Gemini API (subject to rate limits).
-   **Paid Tier**: If you exceed free limits or use a paid billing account, costs are estimated at **£0.0005 - £0.002 per analysis** (based on typical prompt token input/output).
-   **Optimization**: This integration runs **once every 24 hours** by default to minimize costs/usage.

## Privacy & GDPR (UK/EU)

This integration is designed with **Data Minimisation** principles:

1.  **Local Aggregation**: We calculate weekly averages (e.g., "Average Temp: 19.5C") locally on your Home Assistant.
2.  **No Raw History**: Your precise timestamps (e.g., "Living room 20C at 14:02") are **NEVER** sent to the cloud.
3.  **Debug Data**: The internal debug payload (`raw_sample_debug`) is strictly stripped before API transmission.

**Data Transmitted**:
-   Weekly sensor averages/totals.
-   House size and bedroom count.
-   Country ("UK" by default).

**Data Controller**: You are the data controller. Google acts as the processor for the AI generation. Please review [Google's Generative AI Terms of Service](https://policies.google.com/terms).

## Automations & Services

### Services

You can manually trigger a health report update (instead of waiting for the 24h cycle) using the service `ha_genie.generate_report`.

### Automations

The integration exposes a discoverable "Device Trigger" for automations:
- **Trigger**: "Report Ready" (Fires when a new analysis is completed)

Example:
```yaml
automation:
  - alias: "HA Genie Report Notification"
    trigger:
      - platform: device
        domain: ha_genie
        device_id: <YOUR_DEVICE_ID>
        type: report_completed
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Home Health: {{ trigger.event.data.status }}"
          message: "{{ trigger.event.data.summary }}"
```

### Legacy Events
For backward compatibility, the integration still fires the `ha_genie_report_ready` event directly.

```yaml
automation:
  - alias: "Legacy Event Automation"
    trigger:
      - platform: event
        event_type: ha_genie_report_ready
    ...
```

## Troubleshooting

-   **"Unknown" State**: The sensor says "Unknown" or "Initializing" immediately after restart. *Wait up to 24 hours or call the `ha_genie.refresh` service manually.*
-   **API Errors**: Check your logs (`Settings -> System -> Logs`) for "Gemini API Error". Ensure your API key is valid and has billing enabled if required.
