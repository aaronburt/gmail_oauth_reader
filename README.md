# 📬 Gmail OAuth Reader for Home Assistant

Read emails, extract delivery PINs & 2FA codes, and trigger smart home automations directly from your Gmail account — with 100% local processing and official Google OAuth 2.0 security.

---

## ✨ Why You'll Love It

- 🔑 **Automatic 2FA & Delivery PINs**: Instantly pulls verification codes from Amazon, Iceland, DPD, Royal Mail, Steam, Google, and banks.
- 📋 **One-Tap "Copy Code" Mobile Alert**: Includes a pre-built Blueprint that sends actionable alerts to your phone with a button to copy the code directly to your clipboard.
- 🚦 **Smart Queue (No Automation Spam)**: If 5 emails arrive at the same time, they are processed one-by-one with a gentle pause so your notifications and automations run smoothly.
- 🖱️ **Zero YAML Required**: Full support for Home Assistant's visual Automation Builder with native triggers (`New email received`, `New 2FA code received`).
- 🧪 **One-Click Simulator**: Tap the "Simulate Test Email" button anytime to test your automations and dashboard without waiting for real emails.
- 🛡️ **Self-Healing Repairs**: If your Google login ever expires, a 1-click prompt appears in your Home Assistant **Repairs** dashboard to reconnect in seconds.
- 📊 **Beautiful Lovelace Dashboard Card**: Comes with a ready-to-use inbox card showing unread counts, recent emails, and active verification codes.
- 🔒 **100% Private**: Your credentials and emails stay between your Home Assistant instance and Google. No middleman or third-party servers.

---

## 📋 Table of Contents

1. [Quick Start (3 Easy Steps)](#-quick-start)
2. [Step 1: Google Cloud Setup](#step-1-google-cloud-setup)
3. [Step 2: Install the Integration](#step-2-install-the-integration)
4. [Step 3: Add Integration in Home Assistant](#step-3-add-integration-in-home-assistant)
5. [🧪 Test Your Setup in 10 Seconds](#-test-your-setup-in-10-seconds)
6. [📱 Blueprint: Instant 2FA Mobile Notifications](#-blueprint-instant-2fa-mobile-notifications)
7. [📊 Add the Inbox Dashboard Card](#-add-the-inbox-dashboard-card)
8. [🤖 Automation Examples](#-automation-examples)
9. [⚙️ Settings & Customization](#-settings--customization)
10. [🛠️ Troubleshooting & Token Expiry](#-troubleshooting--token-expiry)
11. [🤖 Disclaimer](#-disclaimer)

---

## 🚀 Quick Start

Getting started takes about 5 minutes. You only need:
1. A Google Account.
2. A free Google Cloud project to get your **Client ID** and **Client Secret**.
3. Home Assistant (2024.11 or newer recommended).

---

### Step 1: Google Cloud Setup

Google requires an OAuth Client ID so Home Assistant can securely talk to your inbox.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and sign in.
2. Click the project dropdown in the top bar and click **New Project**. Name it Home Assistant Gmail and click **Create**.
3. Make sure your new project is selected, then go to **APIs & Services** > **Library**.
4. Search for **Gmail API**, click on it, and click **Enable**.

#### Configure the Consent Screen
1. Go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** (for @gmail.com accounts) and click **Create**.
3. Fill in the basics:
   - **App name**: Home Assistant Gmail
   - **User support email**: Select your email address.
   - **Developer contact information**: Enter your email address.
   - Click **Save and Continue**.
4. On the **Scopes** page:
   - Click **Add or Remove Scopes**.
   - In the filter/search box, add: https://www.googleapis.com/auth/gmail.modify
   - *(Optional)* If you want Home Assistant to be able to send emails, also add: https://www.googleapis.com/auth/gmail.send
   - Click **Update**, then click **Save and Continue**.
5. On the **Test users** page:
   - Click **Add Users** and enter your personal Gmail address.
   - Click **Save and Continue**.

> [!IMPORTANT]
> Because your Google Cloud project is in "Testing" mode, Google requires your personal email to be added under **Test users**. This ensures you can log in without needing official app verification from Google.

#### Create Your Credentials
1. Go to **APIs & Services** > **Credentials**.
2. Click **Create Credentials** at the top and select **OAuth client ID**.
3. Set **Application type** to **Web application**.
4. Under **Authorized redirect URIs**, click **Add URI** and enter:
   ```text
   https://my.home-assistant.io/redirect/oauth
   ```
   *(If you do not use My Home Assistant, enter `http://<YOUR_HA_IP>:8123/auth/external/callback` instead).*
5. Click **Create**.
6. A popup will display your **Client ID** and **Client Secret**. Keep this window open or copy them down!

---

### Step 2: Install the Integration

Copy the `custom_components/gmail_oauth_reader` folder into your Home Assistant `/config/custom_components/` directory:

```text
/config/
└── custom_components/
    └── gmail_oauth_reader/
```

Restart Home Assistant after copying the folder.

---

### Step 3: Add Integration in Home Assistant

1. In Home Assistant, go to **Settings** > **Devices & Services**.
2. Click **Add Integration** in the bottom right.
3. Search for **Gmail OAuth Reader** and select it.
4. When prompted, paste your **Client ID** and **Client Secret** from Google Cloud.
5. A Google login tab will open:
   - Choose your Google account.
   - Click **Continue** if Google shows an "App isn't verified" screen (this is normal for your own private app).
   - Click **Allow** to grant permission.
6. Return to Home Assistant — your Gmail account is now linked! 🎉

---

## 🧪 Test Your Setup in 10 Seconds

You don't need to wait for a real email to verify everything is working!

1. Go to **Settings** > **Devices & Services** > **Gmail OAuth Reader**.
2. Click on your device (`Gmail (your_email@gmail.com)`).
3. Under **Diagnostic**, find the **Simulate Test Email** button and click **Press**.
4. Watch your entities update immediately:
   - `sensor.gmail_latest_email` shows the simulated email.
   - `sensor.gmail_latest_otp` displays a simulated 6-digit verification code.

---

## 📱 Blueprint: Instant 2FA Mobile Notifications

We include a pre-made Home Assistant automation blueprint that automatically sends incoming verification codes and delivery PINs to your phone with a **Copy Code** button.

### How to use it:
1. Copy [`blueprints/automation/gmail_otp_actionable.yaml`](blueprints/automation/gmail_otp_actionable.yaml) to your Home Assistant `/config/blueprints/automation/` folder.
2. In Home Assistant, go to **Settings** > **Automations & Scenes** > **Blueprints**.
3. Find **Gmail 2FA / OTP Actionable Notification** and click **Create Automation**.
4. Select your **OTP Sensor** (`sensor.gmail_latest_otp`) and your phone from the dropdown.
5. Click **Save**.

Now whenever an Amazon delivery password, Iceland delivery PIN, or 2FA code arrives in your email, your phone receives an alert with a button that copies the code directly to your clipboard!

---

## 📊 Add the Inbox Dashboard Card

A complete, responsive Lovelace card is included in [`lovelace/gmail_inbox_card.yaml`](lovelace/gmail_inbox_card.yaml).

### How to add it:
1. Open any Home Assistant dashboard.
2. Click the three dots in the top-right corner and select **Edit Dashboard**.
3. Click **Add Card** (at the bottom) and choose **Manual** (at the very bottom).
4. Copy and paste the contents of [`lovelace/gmail_inbox_card.yaml`](lovelace/gmail_inbox_card.yaml) into the box.
5. Click **Save**.

### What you get:
- 📬 **Live Unread Count** badge and queue depth status.
- ⚡ **1-Tap "Poll Now" button** to check for new mail on demand.
- 🔑 **Prominent 2FA / OTP Banner** that lights up with monospace code and a "Mark as Read" button whenever a code arrives.
- 📜 **Recent Emails Feed** showing the sender, subject, and preview of your latest emails.

---

## 🤖 Automation Examples

### 1. Visual Automation Builder (No YAML)
You can build automations using Home Assistant's friendly point-and-click editor:

1. Go to **Settings** > **Automations & Scenes** > **Create Automation**.
2. Under **When**, choose **Device**.
3. Select your **Gmail** device.
4. Choose your trigger:
   - **New email received**
   - **New 2FA / OTP verification code received**
5. Add your actions (e.g., turn on a light, play a chime, send a notification).

---

### 2. Simple Incoming Email Notification (YAML)
Send a notification to your phone whenever an email arrives:

```yaml
alias: "Gmail: New Email Alert"
trigger:
  - platform: state
    entity_id: sensor.gmail_latest_email
    not_to:
      - "idle"
      - "unknown"
      - "unavailable"
action:
  - action: notify.notify
    data:
      title: "New email from {{ state_attr('sensor.gmail_latest_email', 'sender_name') }}"
      message: "{{ state_attr('sensor.gmail_latest_email', 'subject') }}"
```

---

### 3. Send Camera Snapshot via Email (YAML)
If you enabled Write Access during setup, Home Assistant can send outbound emails with attachments:

```yaml
alias: "Security: Email Driveway Snapshot"
trigger:
  - platform: state
    entity_id: binary_sensor.driveway_motion
    to: "on"
action:
  - action: camera.snapshot
    target:
      entity_id: camera.driveway
    data:
      filename: "/config/www/driveway_snapshot.jpg"
  - action: gmail_oauth_reader.send_email
    data:
      to: "my_email@gmail.com"
      subject: "Motion Detected at Driveway"
      body: "Motion was detected. Snapshot is attached."
      attachments:
        - "/config/www/driveway_snapshot.jpg"
```

---

## ⚙️ Settings & Customization

You can fine-tune how the integration behaves anytime without restarting:
1. Go to **Settings** > **Devices & Services** > **Gmail OAuth Reader**.
2. Click **Configure**.

| Setting | Default | What it does |
| :--- | :--- | :--- |
| **Polling interval** | `60 seconds` | How often Home Assistant checks your inbox (between 30 and 600 seconds). |
| **Queue dwell time** | `5 seconds` | Time spent highlighting each email before moving to the next. Gives automations time to react. |
| **Search query filter** | `is:unread label:INBOX` | Standard Gmail search query. Customize it to filter your mail (e.g. `is:unread -category:promotions`). |
| **Extract 2FA / OTP codes** | `Enabled` | Automatically detects verification codes and delivery PINs. |
| **OTP code expiration** | `15 minutes` | How long the 2FA code stays active in the sensor before resetting to `'idle'`. |
| **Enable Write Access** | `Disabled` | Allows Home Assistant to send outbound emails via the `gmail_oauth_reader.send_email` action. |

---

## 🛠️ Troubleshooting & Token Expiry

### 1-Click Native Repairs
If your Google authorization ever lapses, Home Assistant's native **Repairs** dashboard (**Settings** > **System** > **Repairs**) will alert you:
- Simply click **Submit** on the repair card to launch the Google re-authentication popup.
- Once completed, polling resumes automatically and the repair alert disappears!

### Understanding the 7-Day Google Token Expiry
Google Cloud projects that have an OAuth consent screen in **Testing** status automatically expire OAuth refresh tokens after **7 days** unless:
1. Your Google Cloud project is published to **Production** status (takes 1 minute in the OAuth consent screen tab, no review needed for personal use).
2. Or you simply click the 1-click Repair flow when notified.

### Download Diagnostics
If you ever run into an issue, go to **Settings** > **Devices & Services** > **Gmail OAuth Reader** > **three dots** > **Download diagnostics**. All personal emails, tokens, and verification codes are automatically redacted so you can safely share the log on GitHub.

---

## 🤖 Disclaimer

This project was built with AI assistance and thoroughly tested, verified, and reviewed by a human.

