import asyncio
import os

from telebot import types
from telebot.async_telebot import AsyncTeleBot
from dotenv import load_dotenv

from src.send_requests import SendExec
from src.llm import setup_database

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("No BOT_TOKEN provided in environment variables")

bot = AsyncTeleBot(TOKEN)
my_send = SendExec(bot)


@bot.message_handler(commands=['start'])
async def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_myfridges = types.KeyboardButton('/myfridges')
    btn_help = types.KeyboardButton('/help')
    markup.add(btn_myfridges, btn_help)
    await bot.send_message(
        message.chat.id,
        "👋 Привет! Это твой Prompt-Pepper.\nЯ Шеф-ассистент для создания подходящих рецептов на основе ваших предпочтений и содержимого холодильника." + \
            "\nВыбирай холодильник и управляй продуктами. А если вдруг не знаешь, что приготовить, я помогу с рецептами!"+ \
            "\nЧтобы начать, нажми на кнопку /myfridges чтобы просмотреть твои холодильники.",
        reply_markup=markup
    )


@bot.message_handler(commands=['help'])
async def help_request(message):
    await bot.send_message(
        message.chat.id,
        "❓ Доступные команды:\n"
        "/myfridges — показать твои холодильники\n"
        "/help — помощь\n"
        "/clear - очистить историю диалога с нейросетью\n"
        "Чтобы задать вопрос шеф-ассистенту, просто напиши его в чат после выбора холодильника."
    )


@bot.message_handler(commands=['myfridges'])
async def my_fridges(message):
    await my_send.show_fridges_buttons(message)


@bot.message_handler(commands=['clear'])
async def clear_conversation(message):
    await my_send.clear_conversation(message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("fridge_"))
async def fridge_selected(call):
    await my_send.handle_fridge_selection(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("action_"))
async def fridge_action(call):
    await my_send.handle_fridge_action(call)


@bot.message_handler(func=lambda m: True, content_types=['text'])
async def default_handler(message):
    await my_send.handle_text_response(message)


@bot.callback_query_handler(func=lambda call: call.data == "new_fridge")
async def new_fridge(call):
    await my_send.handle_new_fridge(call)


@bot.callback_query_handler(func=lambda call: call.data == "delete_fridge")
async def delete_fridge(call):
    await my_send.handle_delete_fridge(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("removefridge_"))
async def confirm_delete(call):
    await my_send.handle_confirm_delete(call)


async def main():
    await asyncio.to_thread(setup_database)
    print("✅ Bot is running...")
    await bot.infinity_polling(allowed_updates=['message', 'callback_query'])


if __name__ == "__main__":
    asyncio.run(main())
