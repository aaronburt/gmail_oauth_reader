from typing import Final

DOMAIN: Final = "gmail_oauth_reader"

GMAIL_MESSAGES_URL: Final = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
GMAIL_PROFILE_URL: Final = "https://gmail.googleapis.com/gmail/v1/users/me/profile"

SCOPES: Final = ["https://www.googleapis.com/auth/gmail.modify"]

CONF_QUERY: Final = "query"
DEFAULT_QUERY: Final = "is:unread label:INBOX"

CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_QUEUE_DWELL_TIME: Final = "queue_dwell_time"
DEFAULT_DOWNLOAD_DIR: Final = "www/gmail_attachments"

DEFAULT_POLL_INTERVAL: Final = 60
DEFAULT_QUEUE_DWELL_TIME: Final = 5

MIN_POLL_INTERVAL: Final = 30
MAX_POLL_INTERVAL: Final = 600

MIN_QUEUE_DWELL_TIME: Final = 1
MAX_QUEUE_DWELL_TIME: Final = 60

STATE_IDLE: Final = "idle"

MAX_SEEN_CACHE_SIZE: Final = 500
MAX_BODY_PREVIEW_LENGTH: Final = 200
MAX_RECENT_EMAILS: Final = 20
