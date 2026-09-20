import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import BOT_TOKEN
from app.handlers import checklists, link
from app.i18n import STRINGS

logging.basicConfig(level=logging.INFO)


def _commands(lang: str) -> list[BotCommand]:
    """Build the /start and /today command list for *lang*."""
    s = STRINGS[lang]
    return [
        BotCommand(command="start", description=s["cmd_start_desc"]),
        BotCommand(command="today", description=s["cmd_today_desc"]),
    ]


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(link.router)
    dp.include_router(checklists.router)

    # Register localised command menus so each user sees their own language
    # in the Telegram UI.  The language-less call at the end sets the global
    # fallback (English) for all other locales.
    await bot.set_my_commands(_commands("ru"), language_code="ru")
    await bot.set_my_commands(_commands("uz"), language_code="uz")
    await bot.set_my_commands(_commands("en"))  # default fallback for all others

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
