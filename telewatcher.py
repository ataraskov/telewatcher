#!/usr/bin/env python3
"""
telewatcher — monitors Telegram chats for keywords matches.
"""

import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from telethon import TelegramClient, events
from telethon.tl.types import (
    Channel,
    Chat,
    MessageMediaDocument,
    MessageMediaPhoto,
    User,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config(path: str | None = None) -> tuple[dict, Path]:
    if path is None:
        path = (
            sys.argv[1]
            if len(sys.argv) > 1
            else os.environ.get("CONFIG_PATH", "config.yaml")
        )
    config_path = Path(path)
    if not config_path.exists():
        log.error("Config file not found: %s", path)
        sys.exit(1)
    with config_path.open() as f:
        return yaml.safe_load(f), config_path.parent


def find_keywords(text: str, keywords: list[str]) -> list[str]:
    """Return which keywords appear in text (case-insensitive)."""
    lower = text.lower()
    return [kw for kw in keywords if kw.lower() in lower]


# Characters a Markdown renderer treats as formatting. Telegram usernames and
# t.me links are full of underscores, which would otherwise be swallowed as
# emphasis markers (@shkurko_roman -> @shkurkoroman).
_MARKDOWN_SPECIALS = re.compile(r"([\\`*_{}\[\]()#+\-.!>|~])")

PLAIN_CONTENT_TYPE = "text/plain"
MARKDOWN_CONTENT_TYPE = "text/markdown"


def escape_markdown(text: str) -> str:
    """Backslash-escape characters that a Markdown renderer would eat."""
    return _MARKDOWN_SPECIALS.sub(r"\\\1", text)


def build_gotify_body(
    keywords_str: str,
    link: str | None,
    text: str,
    markdown: bool = False,
) -> str:
    """Compose the Gotify notification body for the configured content type."""
    if not markdown:
        parts = [f"Keywords: {keywords_str}"]
        if link:
            parts.append(f"Link: {link}")
        parts.append(f"\n{text}")
        return "\n".join(parts)

    parts = [f"Keywords: {escape_markdown(keywords_str)}"]
    if link:
        # Inline link: the destination is not parsed for emphasis, so the
        # underscores in the chat username survive.
        parts.append(f"Link: [{escape_markdown(link)}]({link})")
    # Two trailing spaces force hard line breaks, keeping the original layout.
    parts.append("\n" + escape_markdown(text).replace("\n", "  \n"))
    return "\n".join(parts)


def chat_display_name(entity) -> str:
    if isinstance(entity, Channel):
        return f"{'Channel' if entity.broadcast else 'Group'} «{entity.title}»"
    if isinstance(entity, Chat):
        return f"Group «{entity.title}»"
    if isinstance(entity, User):
        name = " ".join(filter(None, [entity.first_name, entity.last_name]))
        return f"User {name}" + (f" (@{entity.username})" if entity.username else "")
    return str(entity)


def media_label(message) -> str:
    if isinstance(message.media, MessageMediaPhoto):
        return "[photo] "
    if isinstance(message.media, MessageMediaDocument):
        return "[file] "
    if message.media:
        return "[media] "
    return ""


def build_message_link(chat, message_id: int) -> str | None:
    """Return a t.me deep link for the message, if the chat has a username."""
    username = getattr(chat, "username", None)
    if username:
        return f"https://t.me/{username}/{message_id}"
    return None


async def send_gotify(
    url: str,
    token: str,
    title: str,
    message: str,
    priority: int = 5,
    content_type: str = PLAIN_CONTENT_TYPE,
    extras: dict | None = None,
) -> None:
    payload: dict = {"title": title, "message": message, "priority": priority}
    # Always state the content type: clients that default to Markdown would
    # otherwise mangle links and @usernames.
    payload["extras"] = {
        "client::display": {"contentType": content_type},
        **(extras or {}),
    }
    async with httpx.AsyncClient() as http:
        try:
            resp = await http.post(
                f"{url.rstrip('/')}/message",
                params={"token": token},
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            log.warning("Gotify notification failed: %s", e)


async def build_notification(client: TelegramClient, event, matched: list[str]) -> str:
    """Compose a human-readable notification string."""
    chat = await event.get_chat()
    sender = await event.get_sender()

    chat_name = chat_display_name(chat)
    if isinstance(sender, User):
        sender_name = " ".join(filter(None, [sender.first_name, sender.last_name]))
        if sender.username:
            sender_name += f" (@{sender.username})"
    else:
        sender_name = getattr(sender, "title", str(sender))

    ts = event.message.date.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    keywords_str = ", ".join(f"«{k}»" for k in matched)
    text_preview = (event.message.text or "")[:300]
    media = media_label(event.message)

    lines = [
        f"Keyword match: {keywords_str}",
        f"Chat: {chat_name}",
        f"From: {sender_name}",
        f"Time: {ts}",
        f"Message: {media}{text_preview}",
    ]
    return "\n".join(lines)


async def resolve_chats(client: TelegramClient, chat_specs: list) -> list:
    """Resolve each entry in watch list to a Telegram entity."""
    entities = []
    for spec in chat_specs:
        try:
            entity = await client.get_entity(spec)
            entities.append(entity)
            log.info("Watching: %s", chat_display_name(entity))
        except Exception as e:
            log.warning("Could not resolve chat %r: %s", spec, e)
    return entities


async def main():
    cfg, config_dir = load_config()

    api_id: int = cfg["api_id"]
    api_hash: str = cfg["api_hash"]
    phone: str = cfg["phone"]
    keywords: list[str] = cfg["keywords"]
    watch_specs: list = cfg["watch"]
    notify_chat_spec = cfg.get("notify_chat")
    session_name: str = str(config_dir / cfg.get("session_name", "telewatcher"))

    # `or {}` so a present-but-empty "gotify:" block in an existing config
    # does not blow up on startup.
    gotify_cfg = cfg.get("gotify") or {}
    gotify_url: str | None = gotify_cfg.get("url")
    gotify_token: str | None = gotify_cfg.get("token")
    gotify_priority: int = gotify_cfg.get("priority", 5)
    gotify_content_type: str = gotify_cfg.get("content_type", PLAIN_CONTENT_TYPE)

    if not keywords:
        log.error("No keywords configured.")
        sys.exit(1)
    if not watch_specs:
        log.error("No chats configured to watch.")
        sys.exit(1)
    if not notify_chat_spec and not (gotify_url and gotify_token):
        log.error("No notification target configured (notify_chat or gotify).")
        sys.exit(1)
    if gotify_content_type not in (PLAIN_CONTENT_TYPE, MARKDOWN_CONTENT_TYPE):
        log.error(
            "Invalid gotify.content_type %r (expected %r or %r).",
            gotify_content_type,
            PLAIN_CONTENT_TYPE,
            MARKDOWN_CONTENT_TYPE,
        )
        sys.exit(1)

    client = TelegramClient(session_name, api_id, api_hash)

    await client.start(phone=phone)
    log.info("Signed in as: %s", await client.get_me())

    # Resolve Telegram notification target (optional)
    notify_entity = None
    if notify_chat_spec:
        try:
            notify_entity = await client.get_entity(notify_chat_spec)
            log.info("Telegram notifications → %s", chat_display_name(notify_entity))
        except Exception as e:
            log.error("Cannot resolve notify_chat %r: %s", notify_chat_spec, e)
            sys.exit(1)

    if gotify_url and gotify_token:
        log.info("Gotify notifications → %s", gotify_url)

    # Resolve watched chats and collect their IDs
    watched_entities = await resolve_chats(client, watch_specs)
    if not watched_entities:
        log.error("No valid chats to watch. Exiting.")
        sys.exit(1)

    log.info(
        "Watching %d chat(s) for %d keyword(s): %s",
        len(watched_entities),
        len(keywords),
        ", ".join(f"«{k}»" for k in keywords),
    )

    @client.on(events.NewMessage(chats=watched_entities))
    async def handler(event):
        text = event.message.text or ""
        matched = find_keywords(text, keywords)
        if not matched:
            return

        log.info(
            "Match in chat %s — keywords: %s",
            event.chat_id,
            ", ".join(matched),
        )

        chat = await event.get_chat()
        notification = await build_notification(client, event, matched)
        link = build_message_link(chat, event.message.id)

        # Telegram forwarding
        if notify_entity is not None:
            try:
                await client.forward_messages(notify_entity, event.message)
            except Exception as e:
                log.warning("Could not forward message: %s", e)
            # parse_mode=None: Telethon parses Markdown by default, which
            # would strip the underscores out of links and @usernames.
            await client.send_message(notify_entity, notification, parse_mode=None)

        # Gotify push notification
        if gotify_url and gotify_token:
            keywords_str = ", ".join(matched)
            text_preview = (event.message.text or "")[:500]
            gotify_body = build_gotify_body(
                keywords_str,
                link,
                text_preview,
                markdown=gotify_content_type == MARKDOWN_CONTENT_TYPE,
            )

            await send_gotify(
                url=gotify_url,
                token=gotify_token,
                title=f"{keywords_str}",
                message=gotify_body,
                priority=gotify_priority,
                content_type=gotify_content_type,
            )

    log.info("Listening for messages… (Ctrl+C to stop)")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")
