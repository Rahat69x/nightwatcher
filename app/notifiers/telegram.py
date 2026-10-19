"""
NightWatcher — Telegram notifier
Sends alert with inline keyboard: ✅ Acknowledge | 🚫 Block IP | 📋 Details | 🔕 Ignore
Uses python-telegram-bot in non-async Bot mode for simplicity.
"""
from __future__ import annotations
import logging
from typing import Optional

from app.config import get_settings
from app.models import Alert, Severity

log = logging.getLogger(__name__)
settings = get_settings()

SEVERITY_EMOJI = {
    Severity.LOW: "🔵",
    Severity.MEDIUM: "🟡",
    Severity.HIGH: "🟠",
    Severity.CRITICAL: "🔴",
}


def _format_message(alert: Alert, escalation: bool = False) -> str:
    emoji = SEVERITY_EMOJI.get(alert.severity, "⚪")
    prefix = "⬆️ *ESCALATED* — no response received\n\n" if escalation else ""
    return (
        f"{prefix}{emoji} *NightWatcher Alert #{alert.id}*\n\n"
        f"*{alert.summary}*\n\n"
        f"📊 Severity: `{alert.severity.value.upper()}`\n"
        f"🎯 Score: `{alert.score:.0f}/100`\n"
        f"🔎 Type: `{alert.type}`\n"
        f"🌐 Source: `{alert.source_ip or 'N/A'}`\n"
        f"🔁 Count: `{alert.count}`\n"
        f"⏰ First seen: `{alert.first_seen.strftime('%H:%M UTC') if alert.first_seen else 'N/A'}`"
    )


def _keyboard(alert: Alert) -> list:
    """Inline keyboard with action buttons."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [
        [
            InlineKeyboardButton("✅ Acknowledge", callback_data=f"ack:{alert.id}"),
            InlineKeyboardButton("🚫 Block IP", callback_data=f"block:{alert.id}"),
        ],
        [
            InlineKeyboardButton("📋 Details", callback_data=f"detail:{alert.id}"),
            InlineKeyboardButton("🔕 Ignore", callback_data=f"ignore:{alert.id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


async def send_telegram_alert(alert: Alert, escalation: bool = False) -> None:
    """Send alert to all configured Telegram admin chats."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id_list:
        log.warning("Telegram not configured — skipping")
        return

    try:
        import telegram
        bot = telegram.Bot(token=settings.telegram_bot_token)
        text = _format_message(alert, escalation)
        keyboard = _keyboard(alert)

        async with bot:
            for chat_id in settings.telegram_chat_id_list:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
        log.info(f"Telegram sent for alert {alert.id}")
    except Exception as e:
        log.error(f"Telegram failed for alert {alert.id}: {e}")
        raise


async def send_telegram_text(chat_id: int, text: str) -> None:
    """Utility: send a plain text message to a specific chat."""
    if not settings.telegram_bot_token:
        return
    try:
        import telegram
        bot = telegram.Bot(token=settings.telegram_bot_token)
        async with bot:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        log.error(f"Telegram text send failed: {e}")
