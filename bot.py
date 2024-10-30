import aiofiles
import os
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, Application, ContextTypes

API_TOKEN = 'сюда токен'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Добро пожаловать в бот для анализа логов!")
    await show_option_buttons(update, context)

async def show_option_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Проверить логи", callback_data='check_logs')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Пожалуйста, выберите опцию:', reply_markup=reply_markup)

async def button_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'check_logs':
        await test_logs_command(query.message, context)

async def test_logs_command(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_file_path = os.path.join(os.path.dirname(__file__), 'logs.log')
    if os.path.exists(log_file_path):
        logs = await read_log_file()
        patterns = await read_config()
        filtered_logs = await filter_logs(logs, patterns)

        if filtered_logs:
            max_length = 4096
            for i in range(0, len(filtered_logs), max_length):
                await message.reply_text(filtered_logs[i:i + max_length])
        else:
            await message.reply_text("Нет логов, соответствующих заданным шаблонам.")
    else:
        await message.reply_text("Лог файл не найден.")

async def read_log_file() -> str:
    log_file_path = os.path.join(os.path.dirname(__file__), 'logs.log')
    async with aiofiles.open(log_file_path, 'r') as log_file:
        content = await log_file.read()
    return content

async def read_config() -> list:
    config_file_path = os.path.join(os.path.dirname(__file__), 'config.json')
    async with aiofiles.open(config_file_path, 'r') as config_file:
        config_data = await config_file.read()
    config = json.loads(config_data)
    return config.get('log_patterns', [])

async def filter_logs(logs: str, patterns: list) -> str:
    filtered_logs = []
    for line in logs.splitlines():
        for pattern in patterns:
            if re.search(pattern, line):
                filtered_logs.append(line)
                break
    return '\n'.join(filtered_logs)

def main():
    application = Application.builder().token(API_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_selection_handler, pattern='^check_logs$'))

    application.run_polling()

if __name__ == '__main__':
    main()
