import aiofiles
import os
import json
import re
import logging
import sys
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import asyncio
from os import getenv
from html import escape

API_TOKEN = getenv("BOT_TOKEN")  


dp = Dispatcher()

DEFAULT_LOGS = """2024-10-30T13:20:33+03:00 [INFO] User logged in
2024-10-30T13:20:33+03:00 [DEBUG] Invalid input received
2024-10-30T13:20:33+03:00 [ERROR] User logged out
2024-10-30T13:20:33+03:00 [INFO] User logged in
2024-10-30T13:20:33+03:00 [ERROR] Error processing request
2024-10-30T13:20:34+03:00 [INFO] File uploaded
2024-10-30T13:20:34+03:00 [DEBUG] User logged out
2024-10-30T13:20:34+03:00 [DEBUG] Database connection established
2024-10-30T13:20:34+03:00 [INFO] Database connection established
2024-10-30T13:20:34+03:00 [ERROR] File uploaded
2024-10-30T13:20:34+03:00 [INFO] User logged in
2024-10-30T13:20:34+03:00 [ERROR] Invalid input received
2024-10-30T13:20:34+03:00 [INFO] Invalid input received
2024-10-30T13:20:34+03:00 [DEBUG] File uploaded
"""

DEFAULT_PATTERNS = {
    "log_patterns": [
        "ERROR.*",
        "INFO.*"
    ]
}

@dp.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer("Привет! Выберите опцию ниже:")
    await show_option_buttons(message)

async def show_option_buttons(message: Message) -> None:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Проверить логи 📊", callback_data='check_logs')],
        [InlineKeyboardButton(text="Загрузить логи 📥", callback_data='upload_log')],
        [InlineKeyboardButton(text="Показать логи 📄", callback_data='show_logs')],
        [InlineKeyboardButton(text="Показать шаблоны 📃", callback_data='show_patterns')],
        [InlineKeyboardButton(text="Загрузить шаблоны 🔄", callback_data='upload_patterns')],
        [InlineKeyboardButton(text="Загрузить дефолтные логи и шаблоны ⚙️", callback_data='load_defaults')],
    ])
    await message.answer('Пожалуйста, выберите опцию:', reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == 'delete_pattern')
async def prompt_for_delete_pattern(callback_query: CallbackQuery) -> None:
    await callback_query.message.answer("Пожалуйста, введите шаблон регулярного выражения, который хотите удалить:")


@dp.message(lambda message: message.text and not message.reply_to_message)
async def delete_pattern(message: Message) -> None:
    user_id = message.from_user.id
    pattern_to_delete = message.text.strip()

    
    patterns = await read_user_config(user_id)

    if pattern_to_delete in patterns:
        patterns.remove(pattern_to_delete)  

        config_file_path = os.path.join('logs', f'config_{user_id}.json')

        
        async with aiofiles.open(config_file_path, 'w') as config_file:
            await config_file.write(json.dumps({"log_patterns": patterns}, ensure_ascii=False, indent=4))

        await message.answer("✅ Шаблон успешно удален!")
    else:
        await message.answer("❌ Ошибка: введенный шаблон не найден.")

@dp.callback_query(lambda c: c.data == 'add_pattern')
async def prompt_for_pattern(callback_query: CallbackQuery) -> None:
    await callback_query.message.answer("Пожалуйста, введите ваш шаблон регулярного выражения:")

@dp.message(lambda message: message.text and not message.reply_to_message)
async def save_pattern(message: Message) -> None:
    user_id = message.from_user.id
    pattern = message.text.strip()

    
    try:
        re.compile(pattern)  
    except re.error:
        await message.answer("❌ Ошибка: введенный шаблон некорректен. Попробуйте еще раз.")
        return

    config_file_path = os.path.join('logs', f'config_{user_id}.json')

    
    patterns = await read_user_config(user_id)
    patterns.append(pattern)

    
    async with aiofiles.open(config_file_path, 'w') as config_file:
        await config_file.write(json.dumps({"log_patterns": patterns}, ensure_ascii=False, indent=4))

    await message.answer("✅ Шаблон успешно добавлен!")

@dp.callback_query()
async def button_selection_handler(callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    if callback_query.data == 'check_logs':
        await test_logs_command(callback_query)
    elif callback_query.data == 'upload_log':
        await callback_query.message.answer("Пожалуйста, отправьте файл с логами (.log).")
    elif callback_query.data == 'show_logs':
        await show_logs_command(callback_query)
    elif callback_query.data == 'show_patterns':
        await show_patterns_command(callback_query)
    elif callback_query.data == 'upload_patterns':
        await callback_query.message.answer("Пожалуйста, отправьте файл с шаблонами (JSON).")
    elif callback_query.data == 'load_defaults':
        await load_default_files(callback_query)
    elif callback_query.data == 'delete_logs':
        await delete_logs_command(callback_query)
    elif callback_query.data == 'set_default_patterns':
        await set_default_patterns(callback_query)
    elif callback_query.data == 'delete_pattern':
        await prompt_for_delete_pattern(callback_query)

@dp.message(lambda message: message.document and message.document.file_name.endswith('.log'))
async def handle_document(message: Message) -> None:
    await message.answer("Загрузка файла лога. Пожалуйста, подождите...")  
    user_id = message.from_user.id
    chat_id = message.chat.id
    logging.info(f"Получен user_id: {user_id} и chat_id: {chat_id} при загрузке файла: {message.document.file_name}")

    file_name = f'logs_{user_id}.log'  
    file_path = os.path.join('logs', file_name)

    try:
        document = await message.bot.get_file(message.document.file_id)
        await message.bot.download_file(document.file_path, file_path)

        if os.path.exists(file_path):
            await message.answer("✅ Логи успешно обновлены.")
            logging.info(f"Файл загружен по пути: {file_path}")
        else:
            await message.answer("❌ Ошибка: файл не был загружен.")
    except Exception as e:
        logging.error(f"Ошибка при загрузке файла: {e}")
        await message.answer("🚫 Произошла ошибка при загрузке файла. Пожалуйста, попробуйте еще раз.")

@dp.message(lambda message: message.document and message.document.file_name.endswith('.json'))
async def handle_patterns_upload(message: Message) -> None:
    user_id = message.from_user.id
    file_name = f'config_{user_id}.json'  
    file_path = os.path.join('logs', file_name)

    try:
        document = await message.bot.get_file(message.document.file_id)
        await message.bot.download_file(document.file_path, file_path)

        if os.path.exists(file_path):
            await message.answer("Шаблоны успешно загружены.")
            logging.info(f"Шаблоны загружены по пути: {file_path}")
        else:
            await message.answer("Ошибка: файл не был загружен.")
    except Exception as e:
        logging.error(f"Ошибка при загрузке шаблонов: {e}")
        await message.answer("Произошла ошибка при загрузке шаблонов. Пожалуйста, попробуйте еще раз.")

async def load_default_files(callback_query: CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    
    log_file_path = os.path.join('logs', f'logs_{user_id}.log')
    async with aiofiles.open(log_file_path, 'w') as log_file:
        await log_file.write(DEFAULT_LOGS)

    
    config_file_path = os.path.join('logs', f'config_{user_id}.json')
    async with aiofiles.open(config_file_path, 'w') as config_file:
        await config_file.write(json.dumps(DEFAULT_PATTERNS, ensure_ascii=False, indent=4))

    await callback_query.message.answer("Дефолтные логи и шаблоны успешно загружены.")

async def delete_logs_command(callback_query: CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    log_file_path = os.path.join('logs', f'logs_{user_id}.log')

    if os.path.exists(log_file_path):
        os.remove(log_file_path)
        await callback_query.message.answer("Логи успешно удалены.")
    else:
        await callback_query.message.answer("Логи не найдены.")

async def set_default_patterns(callback_query: CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    config_file_path = os.path.join('logs', f'config_{user_id}.json')

    async with aiofiles.open(config_file_path, 'w') as config_file:
        await config_file.write(json.dumps(DEFAULT_PATTERNS, ensure_ascii=False, indent=4))

    await callback_query.message.answer("Шаблоны по умолчанию успешно установлены.")

async def test_logs_command(callback_query: CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    log_file_path = os.path.join('logs', f'logs_{user_id}.log')
    logging.info(f"Проверка существования файла: {log_file_path}")

    if os.path.exists(log_file_path):
        logging.info(f"Файл найден: {log_file_path}")
        logs = await read_log_file(log_file_path)
        patterns = await read_user_config(user_id)
        filtered_logs = await filter_logs(logs, patterns)

        if filtered_logs:
            max_length = 4096
            for i in range(0, len(filtered_logs), max_length):
                await callback_query.message.answer(filtered_logs[i:i + max_length])
        else:
            await callback_query.message.answer("Нет логов, соответствующих заданным шаблонам.")
    else:
        await callback_query.message.answer("Лог файл не найден.")

async def show_logs_command(callback_query: CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    log_file_path = os.path.join('logs', f'logs_{user_id}.log')

    if os.path.exists(log_file_path):
        logs = await read_log_file(log_file_path)
        if logs:
            await send_long_message(callback_query.message, "📄 Вот ваши логи:\n" + logs)
        else:
            await callback_query.message.answer("🔍 Лог файл пуст. Пожалуйста, загрузите логи или проверьте их наличие.")
    else:
        await callback_query.message.answer("❌ Лог файл не найден. Пожалуйста, загрузите логи перед анализом.")

async def send_long_message(message, text, max_length=4096):
    for i in range(0, len(text), max_length):
        await message.answer("<pre>" + escape(text[i:i + max_length]) + "</pre>", parse_mode=ParseMode.HTML)

async def show_patterns_command(callback_query: CallbackQuery) -> None:
    user_id = callback_query.from_user.id
    patterns = await read_user_config(user_id)

    if patterns:
        max_length = 4096
        patterns_message = "Ваши шаблоны регулярных выражений:\n" + "\n".join(patterns)
        for i in range(0, len(patterns_message), max_length):
            await callback_query.message.answer(patterns_message[i:i + max_length])
    else:
        await callback_query.message.answer("Шаблоны не найдены. Возможно, вы еще не добавили их.")


async def read_log_file(log_file_path: str) -> str:
    try:
        async with aiofiles.open(log_file_path, 'r') as log_file:
            content = await log_file.read()
        return content
    except Exception as e:
        logging.error(f"Ошибка при чтении лог файла: {e}")
        return ""

async def read_user_config(user_id: int) -> list:
    config_file_path = os.path.join('logs', f'config_{user_id}.json')  
    if os.path.exists(config_file_path):
        async with aiofiles.open(config_file_path, 'r') as config_file:
            config_data = await config_file.read()
        config = json.loads(config_data)
        return config.get('log_patterns', [])
    else:
        return []  

async def filter_logs(logs: str, patterns: list) -> str:
    filtered_logs = []
    for line in logs.splitlines():
        for pattern in patterns:
            if re.search(pattern, line):
                filtered_logs.append(line)
                break
    return '\n'.join(filtered_logs)

async def main() -> None:
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    
    os.makedirs('logs', exist_ok=True)

    
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
