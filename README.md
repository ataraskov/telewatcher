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
| `gotify.content_type` | no | `text/plain` (default) or `text/markdown` — how Gotify clients render the body |
| `session_name` | no | Session file name (default: `telewatcher`) |

At least one of `notify_chat` or `gotify` must be configured.

### Message formatting

Notifications are sent without Markdown formatting, so links and `@usernames`
keep their underscores (`https://t.me/serbska_baraholka/1711789`, not
`https://t.me/serbskabaraholka/1711789`). Gotify messages carry an explicit
`text/plain` content type so clients that default to Markdown leave them alone.

Set `gotify.content_type: "text/markdown"` if you prefer a clickable link — the
body is then escaped and line breaks are preserved, so nothing is swallowed by
the renderer.

## Docker

Mount a directory containing `config.yaml` (and the session file) at `/data`:

```bash
docker build -t telewatcher .
docker run -d --restart unless-stopped \
  -v /path/to/data:/data \
  telewatcher
```

The session file is stored alongside the config so it persists across container restarts.

### Prebuilt images

Every push to `master` (or `main`) builds an image and publishes it to
`ghcr.io/ataraskov/telewatcher`:

```bash
docker pull ghcr.io/ataraskov/telewatcher:latest
```

## Versioning

Commits to `master`/`main` are versioned automatically: the workflow takes the
newest `vMAJOR.MINOR.PATCH` tag, bumps the patch, and — once the image has been
built and pushed — tags the commit with it. The first versioned commit becomes
`v0.1.0`.

Each build publishes the same image under several tags, e.g. for `v0.3.4`:

| Tag | Moves |
|-----|-------|
| `0.3.4` | never — pin to this for reproducible deploys |
| `0.3` | with each patch release |
| `latest` | with each commit to the default branch |
| `master` | with each commit to that branch |
| `sha-1a2b3c4` | never — the exact commit |

To bump the minor or major version, push the tag yourself
(`git tag -a v0.4.0 -m "…" && git push origin v0.4.0`); the next automatic
version continues from it.
