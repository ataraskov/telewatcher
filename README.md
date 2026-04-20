# telewatcher

Simple Telegram chats keywords monitoring.

## Features

- Watch multiple chats, groups, or channels simultaneously
- Case-insensitive keyword matching
- Forward matched messages to a Telegram chat
- Push notifications via [Gotify](https://gotify.net/)

## Setup

**1. Get Telegram API credentials**

Create an app at https://core.telegram.org/api/obtaining_api_id to obtain `api_id` and `api_hash`.

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Configure**

```bash
cp config.yaml.example config.yaml
# edit config.yaml with your credentials, chats, and keywords
```

**4. Run**

```bash
python telewatcher.py              # uses config.yaml by default
python telewatcher.py /path/to/config.yaml
CONFIG_PATH=/path/to/config.yaml python telewatcher.py
```

On first run you will be prompted to log in via your phone number. The session is saved so subsequent runs don't require re-authentication.

## Configuration

| Key | Required | Description |
|-----|----------|-------------|
| `api_id` | yes | Telegram API ID |
| `api_hash` | yes | Telegram API hash |
| `phone` | yes | Your phone number (e.g. `+1234567890`) |
| `watch` | yes | List of chats to monitor (usernames, invite links, or numeric IDs) |
| `keywords` | yes | List of keywords to match (case-insensitive) |
| `notify_chat` | no | Telegram chat to forward matches to (e.g. `@me`) |
| `gotify.url` | no | Gotify server URL |
| `gotify.token` | no | Gotify app token |
| `gotify.priority` | no | Notification priority (default: `5`) |
| `session_name` | no | Session file name (default: `telewatcher`) |

At least one of `notify_chat` or `gotify` must be configured.

## Docker

Mount a directory containing `config.yaml` (and the session file) at `/data`:

```bash
docker build -t telewatcher .
docker run -d --restart unless-stopped \
  -v /path/to/data:/data \
  telewatcher
```

The session file is stored alongside the config so it persists across container restarts.
