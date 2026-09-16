# Gmail OAuth Reader for Home Assistant

A production-ready custom Home Assistant integration that securely connects to the Google Gmail REST API via OAuth 2.0. The integration queries unread messages from your inbox, extracts and cleans sender and body details, and sequences incoming messages one-by-one through a paced queue so that Home Assistant automations have dedicated time to process each email.

---

## 1. Google Cloud Platform Configuration

### Project Creation & API Activation
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project named **Home Assistant Gmail**.
3. Open **APIs & Services** > **Library**.
4. Search for and enable both:
   - **Gmail API**
   - **Cloud Pub/Sub API** (only required if using Realtime Push or Pull mode)

### OAuth Consent Screen Setup
1. Go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** (for `@gmail.com` accounts) or **Internal** (if using Google Workspace).
3. Fill in the required fields:
   - **App name**: `Home Assistant Gmail Reader`
   - **User support email**: Select your Google account
   - **Developer contact information**: Enter your email
4. Click **Save and Continue**.
5. On the **Scopes** page, click **Add or Remove Scopes**, manually add:
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/pubsub` (for Pub/Sub Pull mode)
   - `https://www.googleapis.com/auth/gmail.send` (optional: only required if enabling Write Access to send emails)
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
├── blueprints/
│   └── automation/
│       └── gmail_otp_actionable.yaml
└── custom_components/
    └── gmail_oauth_reader/
        ├── __init__.py
        ├── manifest.json
        ├── const.py
        ├── config_flow.py
        ├── coordinator.py
        ├── pubsub.py
        ├── otp.py
        ├── sensor.py
        ├── button.py
        ├── diagnostics.py
        ├── icons.json
        └── translations/
            └── en.json
```

Restart Home Assistant.

### Linking Google Account
1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Gmail OAuth Reader**.
3. If prompted, input your **Client ID** and **Client Secret** obtained from Google Cloud Console.
4. When prompted, choose whether to enable **Write Access** (optional: requests `https://www.googleapis.com/auth/gmail.send` to allow sending emails from Home Assistant).
5. Follow the OAuth prompt to log into Google and grant permissions.
6. Once complete, your Gmail address will appear as the integration entry name.

---

## 3. Realtime Ingestion (Google Cloud Pub/Sub)

The integration supports three update modes:
1. **Polling (Traditional, Default)**: Periodically queries the Gmail API at your configured interval (30–600s). No Google Cloud Pub/Sub setup required.
2. **Google Cloud Pub/Sub (Pull)**: Connects to a Google Cloud Pub/Sub subscription using lightweight asynchronous REST long-polling. Works universally behind NAT and firewalls without requiring an external Home Assistant URL or open ports.
3. **Google Cloud Pub/Sub (Push / Webhook)**: Google Cloud Pub/Sub delivers push notifications directly to a Home Assistant Webhook URL (ideal for setups with Nabu Casa / Cloudflare / public domain).

### Google Cloud Pub/Sub Setup (Optional)
If you want to use Realtime Push or Pull mode:

1. **Create a Pub/Sub Topic**:
   - In Google Cloud Console, go to **Pub/Sub** > **Topics**.
   - Click **Create Topic** (e.g. `gmail-notifications`).
2. **Grant Gmail Publishing Permission**:
   - Select your topic and open the **Permissions** panel.
   - Click **Add Principal**.
   - Enter `gmail-api-push@system.gserviceaccount.com`.
   - Assign the role **Pub/Sub Publisher**.
3. **Configure Subscription**:
   - **For Pull mode**:
     - Under your topic, click **Create Subscription**.
     - Choose **Pull** delivery. Set Subscription ID (e.g. `gmail-sub`).
   - **For Push mode**:
     - In Home Assistant, open integration **Configure** to find your unique Webhook URL (`{webhook_url}`).
     - In Google Cloud Console under your topic, click **Create Subscription**.
     - Choose **Push** delivery and enter your Home Assistant Webhook URL as the endpoint URL.
4. **Configure Home Assistant Options**:
   - Open integration **Configure** in Home Assistant.
   - Select your desired **Update mode**.
   - Enter your **Google Cloud Project ID**, **Topic name**, and (for Pull mode) **Subscription ID**.
   - The integration will automatically register a 7-day Gmail watch and renew it every 4 days.

---

## 4. Architecture & Queue Pacing

### Queue Pacing Engine & 2FA Priority Fast-Tracking
When multiple unread emails arrive between polling cycles or in rapid Pub/Sub batches:
- Incoming notifications are debounced within 1.5s to coalesce rapid arrival bursts.
- All new unread message IDs are fetched and pushed into an internal FIFO queue.
- **Priority Fast-Tracking**: Incoming emails containing 2FA or OTP verification codes automatically jump ahead of routine messages to the front of the queue, ensuring near-zero latency dispatch.
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
- **Update mode**: Choose between `Polling (Traditional)`, `Google Cloud Pub/Sub (Pull)`, or `Google Cloud Pub/Sub (Push / Webhook)` (default: Polling).
- **Polling interval**: 30 to 600 seconds (default: 60 seconds, used in Polling mode).
- **Google Cloud project ID / Topic name / Subscription ID**: Required when using Pub/Sub modes.
- **Safety poll interval**: 300 to 86400 seconds (default: 1800 seconds / 30 mins) as a slow backup refresh in Pub/Sub modes.
- **Queue dwell time**: 1 to 60 seconds (default: 5 seconds).
- **Search Query filter**: e.g. `is:unread label:INBOX -category:promotions` (default: `is:unread label:INBOX`).
- **Extract 2FA / OTP verification codes**: Toggle automatic scanning for verification codes and queue fast-tracking (default: enabled).
- **OTP code expiration**: 1 to 60 minutes retention window before the OTP sensor clears back to `'idle'` (default: 15 minutes).
- **Enable Write Access**: Toggle outbound email sending permission. Enabling write access initiates a Google OAuth re-authentication to grant `https://www.googleapis.com/auth/gmail.send`.

---

## 5. Entities & Actions Specification

### Entities
1. **`sensor.gmail_latest_email`**:
   - **State**: Gmail unique `message_id` while active; `'idle'` when queue is clear.
   - **Attributes**: `sender`, `sender_name`, `sender_email`, `subject`, `body_preview`, `received_time`, `message_id`, `otp_code`, `unread_count`, `queue_size`, `messages` (rotating list of last 20 emails, newest first).
2. **`sensor.gmail_latest_otp`**:
   - **State**: The active OTP / 2FA verification code (e.g. `482910`); `'idle'` when expired or empty.
   - **Attributes**: `sender`, `sender_name`, `sender_email`, `subject`, `received_time`, `expires_at`, `service_name` (extracted provider name, e.g. "GitHub", "Google"), `message_id`, `body_preview`.
3. **`sensor.gmail_unread_count`**:
   - **State**: Integer representing total unread emails matching your search query.
   - **State Class**: `measurement` (enables history graphs, gauges, and dashboard badges).
4. **`sensor.gmail_last_polled`**:
   - **State**: Timestamp of when the integration last polled or received an update from the Gmail server.
   - **Device Class**: `timestamp`
   - **Attributes**: `update_mode` (`polling`, `pubsub_pull`, `pubsub_push`), `watch_active` (`true`/`false`), `watch_expiration` (ISO datetime timestamp).
5. **`sensor.gmail_queue_size`**:
   - **State**: Integer count of pending emails waiting in the paced FIFO queue.
   - **State Class**: `measurement`
6. **`button.gmail_poll_now`**:
   - **State**: Timestamp of last button press.
   - **Action**: Triggers an immediate refresh and poll of the Gmail API without waiting for the polling timer.

### Diagnostics
The integration supports Home Assistant's built-in **Download Diagnostics** feature (accessible under **Settings** > **Devices & Services** > **Gmail OAuth Reader**). The exported report sanitizes sensitive OAuth tokens, client secrets, OTP codes, and body snippets while preserving coordinator queue size, unread counts, and polling state for troubleshooting.

### Actions (Services)
- **`gmail_oauth_reader.get_email_content`**:
  Fetches full metadata, plain text body, HTML body, attachments list, `otp_code`, and all raw headers (`SupportsResponse.ONLY`).
- **`gmail_oauth_reader.modify_email`**:
  Modifies labels on an email (e.g. `mark_as_read: true`, `archive: true`, `add_labels: ["..."]`, `remove_labels: ["..."]`).
- **`gmail_oauth_reader.download_attachment`**:
  Downloads an attachment to Home Assistant storage (default: `www/gmail_attachments/<filename>`).
- **`gmail_oauth_reader.send_email`**:
  Sends an outbound email via the Gmail REST API (`SupportsResponse.OPTIONAL`). Supports plain text, HTML, CC, BCC, Reply-To, and local file attachments. Requires write access scope (`https://www.googleapis.com/auth/gmail.send`) enabled by the user. Returns `message_id` and `thread_id`.

---

## 6. Home Assistant Automation Examples

### Example 1: Notification with State Trigger
```yaml
alias: "Gmail - New Incoming Email Notification"
trigger:
  - platform: state
    entity_id: sensor.gmail_latest_email
    not_to:
      - "idle"
      - "unknown"
      - "unavailable"
action:
  - action: persistent_notification.create
    data:
      title: "Email from {{ state_attr('sensor.gmail_latest_email', 'sender') }}"
      message: >-
        **Subject:** {{ state_attr('sensor.gmail_latest_email', 'subject') }}

        {{ state_attr('sensor.gmail_latest_email', 'body_preview') }}
      notification_id: "gmail_{{ trigger.to_state.state }}"
```

### Example 2: Process Full Email & Mark as Read
```yaml
alias: "Gmail - Process and Mark as Read"
trigger:
  - platform: event
    event_type: gmail_oauth_reader_new_email
action:
  # 1. Fetch full email text and HTML body
  - action: gmail_oauth_reader.get_email_content
    data:
      message_id: "{{ trigger.event.data.message_id }}"
    response_variable: email_data

  # 2. Mark email as read
  - action: gmail_oauth_reader.modify_email
    data:
      message_id: "{{ email_data.message_id }}"
      mark_as_read: true
```

### Example 3: 2FA / OTP Verification Code Alert
```yaml
alias: "Gmail - 2FA / OTP Code Alert"
trigger:
  - platform: event
    event_type: gmail_oauth_reader_new_email
condition:
  - condition: template
    value_template: "{{ trigger.event.data.otp_code is defined and trigger.event.data.otp_code != None }}"
action:
  - action: persistent_notification.create
    data:
      title: "2FA Code: {{ trigger.event.data.otp_code }}"
      message: >-
        ### {{ trigger.event.data.sender }}
        **Code:** `{{ trigger.event.data.otp_code }}`

        **Subject:** {{ trigger.event.data.subject }}
      notification_id: "gmail_otp_{{ trigger.event.data.message_id }}"
```

### Example 4: Send Outbound Email with Attachment
```yaml
alias: "Security - Send Snapshot on Alarm Trigger"
trigger:
  - platform: state
    entity_id: alarm_control_panel.home_alarm
    to: "triggered"
action:
  # 1. Capture camera snapshot to local storage
  - action: camera.snapshot
    target:
      entity_id: camera.driveway
    data:
      filename: "/config/www/security_alert.jpg"
  # 2. Send email with attached snapshot
  - action: gmail_oauth_reader.send_email
    data:
      to: "security-alerts@example.com"
      subject: "Security Alarm Triggered - Snapshot Attached"
      body: "The home alarm was triggered. Driveway camera snapshot attached."
      html_body: "<h2>Alarm Triggered</h2><p>Driveway snapshot captured.</p>"
      attachments:
        - "/config/www/security_alert.jpg"
```

---

## 7. Actionable Notification Blueprint

The repository includes a ready-to-use Home Assistant blueprint: [`blueprints/automation/gmail_otp_actionable.yaml`](blueprints/automation/gmail_otp_actionable.yaml).

### Features
- **Triggers**: Listens for state changes on `sensor.gmail_latest_otp` from `'idle'` to an active verification code.
- **Actionable Buttons**:
  - **Copy Code**: Direct mobile clipboard copy action (`action: copy` with `clipboard: "{{ trigger.to_state.state }}"`).
  - **Mark as Read**: Triggers `gmail_oauth_reader.modify_email` to mark the verification email as read and dismiss the notification.
- **Auto-Dismissal**: When `sensor.gmail_latest_otp` transitions back to `'idle'` (upon expiration), the notification is automatically cleared from your device's notification tray.

### Installation
1. Copy `blueprints/automation/gmail_otp_actionable.yaml` into your Home Assistant `/config/blueprints/automation/` directory.
2. In Home Assistant, navigate to **Settings** > **Automations & Scenes** > **Blueprints**.
3. Locate **Gmail 2FA / OTP Actionable Notification** and click **Create Automation**.
4. Select your **OTP Sensor** (`sensor.gmail_latest_otp`) and target **Device to Notify**.
