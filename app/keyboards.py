from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Помощь с дз", callback_data="menu:hw")],
        [InlineKeyboardButton(text="📷 Фото → решить дз", callback_data="menu:photo")],
        [InlineKeyboardButton(text="❓ Ответить на любой вопрос", callback_data="menu:any")],
        [InlineKeyboardButton(text="💎 Подписка", callback_data="menu:sub")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="menu:ref")],
        [InlineKeyboardButton(text="➕ Докупить", callback_data="menu:topup")],
    ])
