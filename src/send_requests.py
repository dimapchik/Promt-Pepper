import json

from telebot import types

from src.api_requests import ApiExec
from src.llm import RAGService


class SendExec:
    def __init__(self, bot):
        self.my_api = ApiExec(bot)
        self.user_states = {}  # {user_id: {step, fridge_id, action, data}}

    # --- Показать холодильники + кнопки "новый/удалить" ---
    def show_fridges_buttons(self, message):
        user = message.from_user.username
        data = self.my_api.data
        fridges = [(fid, f['name']) for fid, f in data.get("fridges", {}).items() if user in f.get("owners")]

        markup = types.InlineKeyboardMarkup()
        for fid, name in fridges:
            markup.add(types.InlineKeyboardButton(text=f"🧊 {name}", callback_data=f"fridge_{fid}"))

        # ➕ / ➖
        markup.add(types.InlineKeyboardButton("➕ Новый холодильник", callback_data="new_fridge"))
        markup.add(types.InlineKeyboardButton("➖ Удалить холодильник", callback_data="delete_fridge"))

        self.my_api.bot.send_message(message.chat.id, "📋 Твои холодильники:", reply_markup=markup)

    # --- Callback: выбрать холодильник ---
    def handle_fridge_selection(self, call):
        fridge_id = call.data.split("_", 1)[1]
        self.user_states[call.from_user.id] = {"fridge_id": fridge_id}
        user = call.from_user.username

        if not self.my_api.check_admin(fridge_id, user):
            self.my_api.bot.answer_callback_query(call.id, "❌ Вы не админ этого холодильника")
            return

        product_list = self.my_api.get_list(fridge_id)
        fridge_name = self.my_api.get_name(fridge_id)
        self.my_api.bot.send_message(call.message.chat.id, f"📦 Продукты холодильника {fridge_name}:\n{product_list}")
        self.my_api.bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Добавить продукт", callback_data=f"action_add_{fridge_id}"))
        markup.add(types.InlineKeyboardButton("➖ Удалить продукт", callback_data=f"action_remove_{fridge_id}"))
        markup.add(types.InlineKeyboardButton("📦 Показать продукты", callback_data=f"action_list_{fridge_id}"))

        self.my_api.bot.send_message(call.message.chat.id, "Выбери действие:", reply_markup=markup)
        self.my_api.bot.answer_callback_query(call.id)

    # --- Callback: новый холодильник ---
    def handle_new_fridge(self, call):
        user_id = call.from_user.id
        self.user_states[user_id] = {"step": "new_fridge_name", "action": "new_fridge"}
        self.my_api.bot.send_message(call.message.chat.id, "✍️ Введи название нового холодильника:")
        self.my_api.bot.answer_callback_query(call.id)

    # --- Callback: удалить холодильник (показать список) ---
    def handle_delete_fridge(self, call):
        user = call.from_user.username
        data = self.my_api.data
        fridges = [(fid, f['name']) for fid, f in data.get("fridges", {}).items() if user in f.get("owners")]

        if not fridges:
            self.my_api.bot.send_message(call.message.chat.id, "❌ У тебя нет холодильников для удаления")
            self.my_api.bot.answer_callback_query(call.id)
            return

        markup = types.InlineKeyboardMarkup()
        for fid, name in fridges:
            markup.add(types.InlineKeyboardButton(f"❌ {name}", callback_data=f"removefridge_{fid}"))

        self.my_api.bot.send_message(call.message.chat.id, "Выбери холодильник для удаления:", reply_markup=markup)
        self.my_api.bot.answer_callback_query(call.id)

    # --- Callback: подтверждение удаления холодильника ---
    def handle_confirm_delete(self, call):
        fridge_id = call.data.split("_", 1)[1]
        result = self.my_api.remove_fridge(fridge_id, call.from_user.username)
        self.my_api.bot.send_message(call.message.chat.id, result)
        self.my_api.bot.answer_callback_query(call.id)

    # --- Callback: действия с продуктами ---
    def handle_fridge_action(self, call):
        parts = call.data.split("_")
        action = parts[1]   # add / remove / list
        fridge_id = parts[2] if len(parts) == 3 else parts[2] + "_" + parts[3]
        user_id = call.from_user.id

        if action == "list":
            product_list = self.my_api.get_list(fridge_id)
            self.my_api.bot.send_message(call.message.chat.id, f"📦 Продукты:\n{product_list}")
            self.my_api.bot.answer_callback_query(call.id)
            return

        # сохраняем состояние
        self.user_states[user_id] = {"step": "name", "fridge_id": fridge_id, "action": action, "data": {}}
        self.my_api.bot.send_message(call.message.chat.id, "✍️ Введи название продукта:")
        self.my_api.bot.answer_callback_query(call.id)

    # --- Обработка текстов (новый холодильник / продукты) ---
    def handle_text_response(self, message):
        user_id = message.from_user.id
        state = self.user_states.get(user_id)
        if not state:
            self.chat_with_llm(message, None)
            return

        action = state.get("action")
        step = state.get("step")
        fridge_id = state.get("fridge_id")

        # --- новый холодильник ---
        if action == "new_fridge":
            if step == "new_fridge_name":
                name = message.text.strip()
                result = self.my_api.create_fridge(name, message.from_user.username)
                self.my_api.bot.send_message(message.chat.id, result)
                self.user_states[user_id] = {"fridge_id": fridge_id}
                return

        # --- добавление продукта ---
        if action == "add":
            if step == "name":
                state["data"]["name"] = message.text.strip()
                state["step"] = "quantity"
                self.my_api.bot.send_message(message.chat.id, "✍️ Введи количество:")
            elif step == "quantity":
                try:
                    state["data"]["quantity"] = int(message.text.strip())
                except ValueError:
                    self.my_api.bot.send_message(message.chat.id, "❗ Нужно число.")
                    return
                state["step"] = "unit"
                self.my_api.bot.send_message(
                    message.chat.id, "✍️ Введи единицу измерения (шт, кг, л...) или оставь пустым:")
            elif step == "unit":
                state["data"]["unit"] = message.text.strip() or "шт"
                state["step"] = "expires"
                self.my_api.bot.send_message(message.chat.id, "✍️ Введи срок годности (YYYY-MM-DD) или оставь пустым:")
            elif step == "expires":
                # ! Как можно оставить пустым???
                state["data"]["expires"] = message.text.strip() or None
                # Чзх сверху
                d = state["data"]
                result = self.my_api.add_product(fridge_id, d["name"], d["quantity"], d["unit"], d["expires"])
                self.my_api.bot.send_message(message.chat.id, result)
                self.user_states[user_id] = {"fridge_id": fridge_id}

        # --- удаление продукта ---
        elif action == "remove":
            if step == "name":
                state["data"]["name"] = message.text.strip()
                state["step"] = "quantity"
                self.my_api.bot.send_message(message.chat.id, "✍️ Введи количество для удаления:")
            elif step == "quantity":
                try:
                    qty = int(message.text.strip())
                except ValueError:
                    self.my_api.bot.send_message(message.chat.id, "❗ Нужно число.")
                    return
                name = state["data"]["name"]
                result = self.my_api.remove_product(fridge_id, name, qty)
                self.my_api.bot.send_message(message.chat.id, result)
                self.user_states[user_id] = {"fridge_id": fridge_id}

        else:
            self.chat_with_llm(message, fridge_id)

    def chat_with_llm(self, message, fridge_id):
        response = self.my_api.bot.send_message(message.chat.id, "⏳ Думаю...")
        user_id = message.from_user.id
        if fridge_id:
            product_list = self.my_api.get_list(fridge_id)
        else:
            product_list = "❌ Пользователь не указал холодильник. " + \
                           "Если информация о содержимом необходима, попроси пользователя *выбрать холодильник* " + \
                           "(у него есть такая опция) или описать их самостоятельно."
        convo = self.my_api.get_conversation(user_id)

        current_msg = [{"role": "user", "content": message.text}]
        self.my_api.add_to_conversation(user_id, "user", message.text)

        temp_system = []
        if not product_list.startswith("❌"):
            temp_system = [{"role": "system", "content": "Содержимое холодильника: \n" + product_list}]
        recipes_prompt = "\n---\n".join([m["content"] for m in convo + current_msg])
        # print(recipes_prompt)
        recipes = RAGService().get_context(recipes_prompt)

        system_prompt = "Ты — кулинарных помощник, который отвечает на вопросы о рецептах. " + \
                        "Всегда отвечай полностью на русском, переводя названия блюд. " + \
                        "Не давай никаких рекомендаций, кроме кулинарных.\n\n" + \
                        "Чтобы ответ был более точным, используй следующую информацию:\n\n" + \
                        "# Содержимое холодильника пользователя:\n" + product_list + "\n\n" + \
                        "# Релевантные рецепты:\n" + recipes + "\n\n"
        system_prompt = [{"role": "system", "content": system_prompt}]

        full_conversation = system_prompt + convo + current_msg

        full_response = ""
        chunk_buffer = ""
        for chunk in RAGService().query_stream(full_conversation):
            full_response += chunk
            chunk_buffer += chunk

            if len(chunk_buffer) >= 50:
                try:
                    self.my_api.bot.edit_message_text(
                        chat_id=response.chat.id,
                        message_id=response.message_id,
                        text=full_response
                    )
                    chunk_buffer = ""
                except Exception:
                    pass

        try:
            if chunk_buffer:
                self.my_api.bot.edit_message_text(
                    chat_id=response.chat.id,
                    message_id=response.message_id,
                    text=full_response
                )
        except Exception:
            pass

        self.my_api.add_to_conversation(user_id, "assistant", full_response)
        # print("✓ Response sent to user.")

    def clear_conversation(self, message):
        user_id = message.from_user.id
        result = self.my_api.clear_conversation(user_id)
        self.my_api.bot.send_message(message.chat.id, result)
