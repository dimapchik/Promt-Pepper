import os

import telebot

from telebot import types
from dotenv import load_dotenv

from src.send_requests import SendExec
from src.llm import setup_database

# Рекомендую хранить токен в env: export BOT_TOKEN="..."
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("No BOT_TOKEN provided in environment variables")

bot = telebot.TeleBot(TOKEN)
my_send = SendExec(bot)


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_myfridges = types.KeyboardButton('/myfridges')
    btn_help = types.KeyboardButton('/help')
    markup.add(btn_myfridges, btn_help)
    bot.send_message(
        message.chat.id,
        "👋 Привет! Это твой Promt-Pepper.\nЯ Шеф-ассистент для создания подходящих рецептов на основе ваших предпочтений и содержимого холодильника." + \
            "\nВыбирай холодильник и управляй продуктами. А если вдруг не знаешь, что приготовить, я помогу с рецептами!"+ \
            "\nЧтобы начать, нажми на кнопку /myfridges чтобы просмотреть твои холодильники.",
        reply_markup=markup
    )


@bot.message_handler(commands=['help'])
def help_request(message):
    bot.send_message(
        message.chat.id,
        "❓ Доступные команды:\n"
        "/myfridges — показать твои холодильники\n"
        "/help — помощь\n"
        "/clear - очистить историю диалога с нейросетью\n"
        "Чтобы задать вопрос шеф-ассистенту, просто напиши его в чат после выбора холодильника."
    )


# --- Шаг 1: показать холодильники ---
@bot.message_handler(commands=['myfridges'])
def my_fridges(message):
    my_send.show_fridges_buttons(message)


@bot.message_handler(commands=['clear'])
def clear_conversation(message):
    my_send.clear_conversation(message)


# --- Callback handler: выбор холодильника ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("fridge_"))
def fridge_selected(call):
    my_send.handle_fridge_selection(call)


# --- Callback handler: выбрать действие для холодильника ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("action_"))
def fridge_action(call):
    my_send.handle_fridge_action(call)


# --- Flow добавления / удаления продуктов ---
@bot.message_handler(func=lambda m: True, content_types=['text'])
def default_handler(message):
    my_send.handle_text_response(message)

# --- Callback: новый холодильник ---
@bot.callback_query_handler(func=lambda call: call.data == "new_fridge")
def new_fridge(call):
    my_send.handle_new_fridge(call)

# --- Callback: удалить холодильник ---
@bot.callback_query_handler(func=lambda call: call.data == "delete_fridge")
def delete_fridge(call):
    my_send.handle_delete_fridge(call)

# --- Callback: подтверждение удаления ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("removefridge_"))
def confirm_delete(call):
    my_send.handle_confirm_delete(call)


setup_database()
print("✅ Bot is running...")
bot.infinity_polling(allowed_updates=['message', 'callback_query'])
