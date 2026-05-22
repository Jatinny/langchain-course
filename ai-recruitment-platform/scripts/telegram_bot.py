"""Telegram bot for recruitment platform notifications and commands."""
import asyncio
import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from common.config import settings
from common.logging import get_logger

logger = get_logger(__name__)

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    keyboard = [
        [
            InlineKeyboardButton("Dashboard", callback_data="dashboard"),
            InlineKeyboardButton("New Discovery", callback_data="discover"),
        ],
        [
            InlineKeyboardButton("Pipeline", callback_data="pipeline"),
            InlineKeyboardButton("Analytics", callback_data="analytics"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(
        f"Welcome to <b>RecruitAI</b>, {user.mention_html()}!\n\n"
        "I'll send you real-time recruitment notifications:\n"
        "• New employer discoveries\n"
        "• Outreach replies\n"
        "• Placement confirmations\n"
        "• Commission alerts\n\n"
        "Use the buttons below or type /help for all commands.",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = """
<b>Available Commands:</b>

📊 <b>Analytics</b>
/dashboard - View today's KPIs
/revenue - Monthly revenue summary
/pipeline - Employer pipeline status

🔍 <b>Discovery</b>
/discover [industry] [region] - Trigger employer discovery
/employers - List top employers
/contacts - Recent recruiter contacts

👥 <b>Candidates</b>
/candidates - List available candidates
/submit [candidate_id] [job_id] - Submit candidate

📧 <b>Outreach</b>
/campaigns - Active campaigns
/responses - Recent replies

💰 <b>Revenue</b>
/commissions - Commission tracker
/placements - Recent placements

⚙️ <b>Settings</b>
/alerts on/off - Toggle notifications
/subscribe [topic] - Subscribe to updates
"""
    await update.message.reply_html(help_text)


async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show dashboard KPIs."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.analytics_service_url}/analytics/dashboard",
                headers={"Authorization": f"Bearer {context.bot_data.get('system_token', '')}"},
                timeout=10.0,
            )
            data = resp.json()
            kpis = data.get("kpis", {})

        message = (
            "📊 <b>Today's Dashboard</b>\n\n"
            f"🏢 Employers: {kpis.get('total_employers', 0)}\n"
            f"📧 Active Campaigns: {kpis.get('active_campaigns', 0)}\n"
            f"✅ Placements (MTD): {kpis.get('placements_mtd', 0)}\n"
            f"💰 Revenue (MTD): ₹{kpis.get('revenue_mtd', 0):,.0f}\n"
            f"🔄 Pipeline Value: ₹{kpis.get('pipeline_value', 0):,.0f}"
        )
    except Exception as e:
        message = f"⚠️ Could not fetch dashboard: {e}"

    await update.message.reply_html(message)


async def discover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger employer discovery."""
    args = context.args
    industry = args[0] if args else "IT Services"
    region = args[1] if len(args) > 1 else "India"

    await update.message.reply_text(
        f"🔍 Starting discovery for {industry} in {region}...\n"
        "I'll notify you when results are ready!"
    )

    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.employer_discovery_url}/discovery/start",
                json={"industries": [industry], "regions": [region], "limit": 50},
                headers={"Authorization": f"Bearer {context.bot_data.get('system_token', '')}"},
                timeout=10.0,
            )
            result = resp.json()
            await update.message.reply_text(
                f"✅ Discovery job started!\nJob ID: {result.get('job_id')}\n"
                f"Estimated time: {result.get('estimated_time_seconds', 60)}s"
            )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Discovery failed: {e}")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    if query.data == "dashboard":
        context.args = []
        await dashboard(update, context)
    elif query.data == "discover":
        await query.edit_message_text("Send: /discover [industry] [region]\nExample: /discover 'IT Services' India")
    elif query.data == "pipeline":
        await query.edit_message_text("Use /pipeline to view employer pipeline stages")
    elif query.data == "analytics":
        await query.edit_message_text("Use /dashboard for full analytics")


# Notification functions (called from Kafka consumer)
async def notify_employer_discovered(bot, chat_id: str, employer_data: dict) -> None:
    """Send employer discovery notification."""
    message = (
        f"🏢 <b>New Employer Found!</b>\n\n"
        f"Company: {employer_data.get('name')}\n"
        f"Industry: {employer_data.get('industry')}\n"
        f"Region: {employer_data.get('region')}\n"
        f"Score: {employer_data.get('score', 0):.1f}/100\n"
        f"Vendor Friendly: {'✅' if employer_data.get('is_vendor_friendly') else '❌'}"
    )
    await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")


async def notify_outreach_replied(bot, chat_id: str, reply_data: dict) -> None:
    """Send reply notification."""
    message = (
        f"📬 <b>Outreach Reply!</b>\n\n"
        f"From: {reply_data.get('contact_name')}\n"
        f"Company: {reply_data.get('company')}\n"
        f"Status: {reply_data.get('sentiment', 'neutral').title()}\n"
        f"Message: {reply_data.get('preview', '')[:100]}..."
    )
    await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")


async def notify_placement_confirmed(bot, chat_id: str, placement_data: dict) -> None:
    """Send placement confirmation notification."""
    message = (
        f"🎉 <b>Placement Confirmed!</b>\n\n"
        f"Candidate: {placement_data.get('candidate_name')}\n"
        f"Employer: {placement_data.get('employer_name')}\n"
        f"Role: {placement_data.get('job_title')}\n"
        f"💰 Commission: ₹{placement_data.get('commission_amount', 0):,.0f}"
    )
    await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")


def create_app() -> Application:
    """Create and configure the Telegram bot application."""
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("discover", discover))
    app.add_handler(CallbackQueryHandler(button_handler))

    return app


if __name__ == "__main__":
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        exit(1)

    application = create_app()
    logger.info("Starting Telegram bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
