# Gmail OAuth Reader for Home Assistant

A production-ready custom Home Assistant integration that securely connects to the Google Gmail REST API via OAuth 2.0. The integration queries unread messages from your inbox, extracts and cleans sender and body details, and sequences incoming messages one-by-one through a paced queue so that Home Assistant automations have dedicated time to process each email.

---

## 1. Google Cloud Platform Configuration

### Project Creation & API Activation
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project named **Home Assistant Gmail**.
3. Open **APIs & Services** > **Library**.
4. Search for **Gmail API** and click **Enable**.

### OAuth Consent Screen Setup
1. Go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** (for `@gmail.com` accounts) or **Internal** (if using Google Workspace).
3. Fill in the required fields:
   - **App name**: `Home Assistant Gmail Reader`
   - **User support email**: Select your Google account
   - **Developer contact information**: Enter your email
4. Click **Save and Continue**.
5. On the **Scopes** page, click **Add or Remove Scopes**, manually add or select:
   - `https://www.googleapis.com/auth/gmail.readonly`
6. Click **Update** and **Save and Continue**.
7. On the **Test users** page, click **Add Users** and enter your personal Gmail address.

> **Important**: In Google Cloud "Testing" status, unverified external apps have refresh tokens that expire after 7 days unless the Google account is explicitly registered in **Test users**.

### OAuth 2.0 Client ID Credentials
1. Go to **APIs & Services** > **Credentials**.
2. Click **Create Credentials** > **OAuth client ID**.
3. Set **Application type** to **Web application**.
4. Set **Name** to `Home Assistant OAuth Client`.
5. Under **Authorized JavaScript origins**, add:
   - `https://my.home-assistant.io`
   - Your local Home Assistant address (e.g., `http://homeassistant.local:8123` or `http://192.168.1.100:8123`)
6. Under **Authorized redirect URIs**, add:
   - **Primary (My Home Assistant)**: `https://my.home-assistant.io/redirect/oauth`
   - **Local / Direct callback**: `http://homeassistant.local:8123/auth/external/callback` (or your public Home Assistant URL with `/auth/external/callback`)
7. Click **Create**.
8. Copy the generated **Client ID** and **Client Secret**.

---

## 2. Installation & Configuration

### Directory Installation
Copy the `custom_components/gmail_oauth_reader` directory into your Home Assistant `/config/custom_components/` directory:

```
/config/
└── custom_components/
    └── gmail_oauth_reader/
        ├── __init__.py
        ├── manifest.json
        ├── const.py
        ├── config_flow.py
        ├── coordinator.py
        ├── sensor.py
        ├── strings.json
        └── translations/
            └── en.json
```

Restart Home Assistant.

### Linking Google Account
1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Gmail OAuth Reader**.
3. If prompted, input your **Client ID** and **Client Secret** obtained from Google Cloud Console.
4. Follow the OAuth prompt to log into Google and grant read-only permission.
5. Once complete, your Gmail address will appear as the integration entry name.

---

## 3. Architecture & Queue Pacing

### Queue Pacing Engine
When multiple unread emails arrive between polling cycles:
- All new unread message IDs are fetched and pushed into an internal FIFO queue.
- The coordinator runs an asynchronous dispatcher that pops each email sequentially.
- The sensor holds that email's state and attributes for a configurable dwell period (default: 5 seconds).
- Once the queue is fully drained, the sensor transitions cleanly to `'idle'`.

### Cold Boot Protection
On initial startup or integration reload:
- Existing unread messages in the inbox are seeded into the in-memory cache and marked as seen.
- This prevents Home Assistant from dumping older inbox backlogs into the queue upon restart.
- Only newly arrived emails after startup are queued and dispatched.

### Options Flow (Dynamic Configuration)
Access the integration's **Configure** button under **Settings** > **Devices & Services** to adjust:
- **Polling interval**: 30 to 600 seconds (default: 60 seconds).
- **Queue dwell time**: 1 to 60 seconds (default: 5 seconds).

---

## 4. Sensor Entity Specification

- **Entity ID**: `sensor.gmail_latest_email` (or `sensor.<email_prefix>_latest_email`)
- **State**: The Gmail unique `message_id` while an email is actively displayed; `'idle'` when no active email is present.

### Attributes
| Attribute | Type | Description |
| :--- | :--- | :--- |
| `sender` | string | Clean sender display name with email fallback |
| `sender_name` | string | Display name of the sender |
| `sender_email` | string | Extracted sender email address |
| `subject` | string | RFC 2047 MIME decoded subject line |
| `body_preview` | string | Plain-text snippet with HTML, URLs, and tracking links stripped |
| `received_time` | string | ISO 8601 formatted timestamp |
| `message_id` | string | Unique Gmail message identifier |
| `unread_count` | integer | Total unread inbox messages matching filter |
| `queue_size` | integer | Number of emails waiting in the dispatch queue |

---

## 5. Home Assistant Automation Example

```yaml
alias: "Gmail - New Incoming Email Notification"
description: "Dispatches a persistent notification whenever a new unread email is processed through the queue"
trigger:
  - platform: state
    entity_id: sensor.gmail_latest_email
    not_to:
      - "idle"
      - "unknown"
      - "unavailable"
condition:
  - condition: template
    value_template: "{{ trigger.to_state.state != trigger.from_state.state }}"
  - condition: template
    value_template: "{{ state_attr('sensor.gmail_latest_email', 'sender') is not none }}"
action:
  - action: persistent_notification.create
    data:
      title: "Email from {{ state_attr('sensor.gmail_latest_email', 'sender') }}"
      message: >-
        **Subject:** {{ state_attr('sensor.gmail_latest_email', 'subject') }}

        {{ state_attr('sensor.gmail_latest_email', 'body_preview') }}
      notification_id: "gmail_{{ trigger.to_state.state }}"
mode: queued
max: 20
```
