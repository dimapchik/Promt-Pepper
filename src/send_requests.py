from telebot import types
from loguru import logger

from src.api_requests import ApiExec
from src.llm import RAGService


class SendExec:
    def __init__(self, bot):
        self.my_api = ApiExec(bot)
        self.user_states = {}  # {user_id: {step, fridge_id, action, data}}

    def escape_markdown(self, text: str) -> str:
        escape_chars = {
            '(': '\\(',
            ')': '\\)',
            '[': '\\[',
            ']': '\\]',
            '{': '\\{',
            '}': '\\}',
            '~': '\\~',
            '`': '\\`',
            '>': '\\>',
            '-': '\\-',
            '=': '\\=',
            '+': '\\+',
            '.': '\\.',
            '!': '\\!',
        }

        text = text.replace('**', '<NeedToPutStars>')
        text = text.replace('* ', '• ')
        text = text.replace('<NeedToPutStars>', '*')
        for char, escaped_char in escape_chars.items():
            text = text.replace(char, escaped_char)
        return text

    async def show_fridges_buttons(self, message):
        user = message.from_user.username
        data = self.my_api.data
        fridges = [(fid, f['name']) for fid, f in data.get("fridges", {}).items() if user in f.get("owners")]

        markup = types.InlineKeyboardMarkup()
        for fid, name in fridges:
            markup.add(types.InlineKeyboardButton(text=f"🧊 {name}", callback_data=f"fridge_{fid}"))

        markup.add(types.InlineKeyboardButton("➕ Новый холодильник", callback_data="new_fridge"))
        markup.add(types.InlineKeyboardButton("➖ Удалить холодильник", callback_data="delete_fridge"))

        await self.my_api.bot.send_message(message.chat.id, "📋 Твои холодильники:", reply_markup=markup)

    async def handle_fridge_selection(self, call):
        fridge_id = call.data.split("_", 1)[1]
        self.user_states[call.from_user.id] = {"fridge_id": fridge_id}
        user = call.from_user.username

        if not self.my_api.check_admin(fridge_id, user):
            await self.my_api.bot.answer_callback_query(call.id, "❌ Вы не админ этого холодильника")
            return

        product_list = self.my_api.get_list(fridge_id)
        fridge_name = self.my_api.get_name(fridge_id)
        await self.my_api.bot.send_message(
            call.message.chat.id,
            f"📦 Продукты холодильника {fridge_name}:\n{product_list}",
        )
        await self.my_api.bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Добавить продукт", callback_data=f"action_add_{fridge_id}"))
        markup.add(types.InlineKeyboardButton("➖ Удалить продукт", callback_data=f"action_remove_{fridge_id}"))
        markup.add(types.InlineKeyboardButton("📦 Показать продукты", callback_data=f"action_list_{fridge_id}"))

        await self.my_api.bot.send_message(call.message.chat.id, "Выбери действие:", reply_markup=markup)

    async def handle_new_fridge(self, call):
        user_id = call.from_user.id
        self.user_states[user_id] = {"step": "new_fridge_name", "action": "new_fridge"}
        await self.my_api.bot.send_message(call.message.chat.id, "✍️ Введи название нового холодильника:")
        await self.my_api.bot.answer_callback_query(call.id)

    async def handle_delete_fridge(self, call):
        user = call.from_user.username
        data = self.my_api.data
        fridges = [(fid, f['name']) for fid, f in data.get("fridges", {}).items() if user in f.get("owners")]

        if not fridges:
            await self.my_api.bot.send_message(call.message.chat.id, "❌ У тебя нет холодильников для удаления")
            await self.my_api.bot.answer_callback_query(call.id)
            return

        markup = types.InlineKeyboardMarkup()
        for fid, name in fridges:
            markup.add(types.InlineKeyboardButton(f"❌ {name}", callback_data=f"removefridge_{fid}"))

        await self.my_api.bot.send_message(
            call.message.chat.id,
            "Выбери холодильник для удаления:",
            reply_markup=markup,
        )
        await self.my_api.bot.answer_callback_query(call.id)

    async def handle_confirm_delete(self, call):
        fridge_id = call.data.split("_", 1)[1]
        result = await self.my_api.remove_fridge(fridge_id, call.from_user.username)
        await self.my_api.bot.send_message(call.message.chat.id, result)
        await self.my_api.bot.answer_callback_query(call.id)

    async def handle_fridge_action(self, call):
        parts = call.data.split("_")
        action = parts[1]   # add / remove / list
        fridge_id = parts[2] if len(parts) == 3 else parts[2] + "_" + parts[3]
        user_id = call.from_user.id

        if action == "list":
            product_list = self.my_api.get_list(fridge_id)
            await self.my_api.bot.send_message(call.message.chat.id, f"📦 Продукты:\n{product_list}")
            await self.my_api.bot.answer_callback_query(call.id)
            return

        self.user_states[user_id] = {"step": "name", "fridge_id": fridge_id, "action": action, "data": {}}
        await self.my_api.bot.send_message(call.message.chat.id, "✍️ Введи название продукта:")
        await self.my_api.bot.answer_callback_query(call.id)

    async def handle_text_response(self, message):
        user_id = message.from_user.id
        state = self.user_states.get(user_id)
        if not state:
            await self.chat_with_llm(message, None)
            return

        action = state.get("action")
        step = state.get("step")
        fridge_id = state.get("fridge_id")

        if action == "new_fridge":
            if step == "new_fridge_name":
                name = message.text.strip()
                result = await self.my_api.create_fridge(name, message.from_user.username)
                await self.my_api.bot.send_message(message.chat.id, result)
                self.user_states[user_id] = {"fridge_id": fridge_id}
                return

        if action == "add":
            if step == "name":
                state["data"]["name"] = message.text.strip()
                state["step"] = "quantity"
                await self.my_api.bot.send_message(message.chat.id, "✍️ Введи количество:")
            elif step == "quantity":
                try:
                    state["data"]["quantity"] = int(message.text.strip())
                except ValueError:
                    await self.my_api.bot.send_message(message.chat.id, "❗ Нужно целое число.")
                    return
                state["step"] = "unit"
                await self.my_api.bot.send_message(
                    message.chat.id, "✍️ Введи единицу измерения (шт, кг, л...) или поставьте \"-\":")
            elif step == "unit":
                state["data"]["unit"] = message.text.strip() or "шт"
                state["step"] = "expires"
                await self.my_api.bot.send_message(
                    message.chat.id,
                    "✍️ Введи срок годности (YYYY-MM-DD) или поставьте \"-\":",
                )
            elif step == "expires":
                state["data"]["expires"] = message.text.strip() or None
                d = state["data"]
                result = await self.my_api.add_product(
                    fridge_id, d["name"], d["quantity"], d["unit"], d["expires"]
                )
                await self.my_api.bot.send_message(message.chat.id, result)
                self.user_states[user_id] = {"fridge_id": fridge_id}

        elif action == "remove":
            if step == "name":
                state["data"]["name"] = message.text.strip()
                state["step"] = "quantity"
                await self.my_api.bot.send_message(message.chat.id, "✍️ Введи количество для удаления:")
            elif step == "quantity":
                try:
                    qty = int(message.text.strip())
                except ValueError:
                    await self.my_api.bot.send_message(message.chat.id, "❗ Нужно целое число.")
                    return
                name = state["data"]["name"]
                result = await self.my_api.remove_product(fridge_id, name, qty)
                await self.my_api.bot.send_message(message.chat.id, result)
                self.user_states[user_id] = {"fridge_id": fridge_id}

        else:
            await self.chat_with_llm(message, fridge_id)

    async def chat_with_llm(self, message, fridge_id):
        response = await self.my_api.bot.send_message(message.chat.id, "⏳ Думаю...")
        user_id = message.from_user.id
        if fridge_id:
            product_list = self.my_api.get_list(fridge_id)
        else:
            product_list = "❌ Пользователь не указал холодильник. " + \
                           "Если информация о содержимом необходима, попроси пользователя *выбрать холодильник* " + \
                           "(у него есть такая опция) или описать их самостоятельно."
        convo = await self.my_api.get_conversation(user_id)

        current_msg = [{"role": "user", "content": message.text}]
        await self.my_api.add_to_conversation(user_id, "user", message.text)

        recipes_prompt = "\n---\n".join([m["content"] for m in convo + current_msg])
        recipes = await RAGService().get_context(recipes_prompt, need_to_translate=True)

        system_prompt = "Ты — кулинарных помощник, который отвечает на вопросы о рецептах. " + \
                        "Всегда отвечай полностью на русском. " + \
                        "Не давай никаких рекомендаций, кроме кулинарных.\n\n" + \
                        "Чтобы ответ был более точным, используй следующую информацию:\n\n" + \
                        "# Содержимое холодильника пользователя:\n" + product_list + "\n\n" + \
                        "# Релевантные рецепты:\n" + recipes + "\n\n"
        system_prompt = [{"role": "system", "content": system_prompt}]

        full_conversation = system_prompt + convo + current_msg

        full_response = ""
        chunk_buffer = ""
        async for chunk in RAGService().query_stream(full_conversation):
            full_response += chunk
            chunk_buffer += chunk

            if len(chunk_buffer) >= 50:
                try:
                    await self.my_api.bot.edit_message_text(
                        chat_id=response.chat.id,
                        message_id=response.message_id,
                        text=full_response
                    )
                    chunk_buffer = ""
                except Exception as e:
                    logger.error(f"Error editing message: {e}")

        try:
            escaped_response = self.escape_markdown(full_response)
            await self.my_api.bot.edit_message_text(
                chat_id=response.chat.id,
                message_id=response.message_id,
                text=escaped_response,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.error(f"Error finalizing message: {e}")
            await self.my_api.bot.edit_message_text(
                chat_id=response.chat.id,
                message_id=response.message_id,
                text="Произошла ошибка, попробуйте повторить запрос"
            )

        await self.my_api.add_to_conversation(user_id, "assistant", full_response)

    async def clear_conversation(self, message):
        user_id = message.from_user.id
        result = await self.my_api.clear_conversation(user_id)
        await self.my_api.bot.send_message(message.chat.id, result)
