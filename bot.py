import asyncio
import logging
import os
import re

import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, BufferedInputFile

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

PINTEREST_RE = re.compile(
    r"(https?://(?:[\w.-]*\.)?pinterest\.[a-z.]+/pin/\S+|https?://pin\.it/\S+)"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get_pinterest_media(url: str):
    """Достаём прямую ссылку на видео или картинку из страницы пина."""
    resp = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    video_tag = soup.find("meta", attrs={"property": "og:video:url"}) or \
        soup.find("meta", attrs={"property": "og:video"})
    if video_tag and video_tag.get("content"):
        return "video", video_tag["content"]

    image_tag = soup.find("meta", attrs={"property": "og:image"})
    if image_tag and image_tag.get("content"):
        return "photo", image_tag["content"]

    return None, None


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Привет! Пришли ссылку на пин с Pinterest "
        "(pinterest.com/pin/... или pin.it/...) — скачаю картинку или видео."
    )


@dp.message(F.text)
async def handle_message(message: Message):
    match = PINTEREST_RE.search(message.text or "")
    if not match:
        await message.answer(
            "Это не похоже на ссылку Pinterest. Нужна ссылка вида "
            "pinterest.com/pin/... или pin.it/..."
        )
        return

    url = match.group(0)
    status_msg = await message.answer("Ищу медиа...")

    try:
        media_type, media_url = get_pinterest_media(url)
    except Exception:
        logging.exception("Failed to parse pinterest page")
        await status_msg.edit_text("Не получилось открыть эту ссылку. Проверь, что она рабочая.")
        return

    if not media_url:
        await status_msg.edit_text("Не нашёл ни видео, ни картинку на этой странице.")
        return

    try:
        if media_type == "video":
            await message.answer_video(video=media_url)
        else:
            await message.answer_photo(photo=media_url)
        await status_msg.delete()
    except Exception:
        # Фоллбек: скачиваем файл сами и отправляем как файл, а не по ссылке
        try:
            file_resp = requests.get(media_url, headers=HEADERS, timeout=30)
            file_resp.raise_for_status()
            filename = "pinterest_video.mp4" if media_type == "video" else "pinterest_image.jpg"
            file = BufferedInputFile(file_resp.content, filename=filename)
            if media_type == "video":
                await message.answer_video(video=file)
            else:
                await message.answer_photo(photo=file)
            await status_msg.delete()
        except Exception:
            logging.exception("Failed to send media")
            await status_msg.edit_text("Скачал ссылку, но не смог отправить файл в Telegram.")


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("Не задана переменная окружения BOT_TOKEN")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
