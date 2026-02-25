from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Домашка")],
            [KeyboardButton(text="🧠 Вопрос")],
            [KeyboardButton(text="🖼 Фото")]
        ],
        resize_keyboard=True
    )
