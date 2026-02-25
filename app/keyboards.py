from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Помощь с дз"), KeyboardButton(text="📷 Загрузить фото и решить дз")],
            [KeyboardButton(text="❓ Ответить на любой вопрос")],
            [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="🎁 Реферальная программа")],
            [KeyboardButton(text="➕ Докупить")],
        ],
        resize_keyboard=True
    )

def back_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад в меню")]],
        resize_keyboard=True
    )

def sub_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Старт — 199 (50/день, 30 дней)", callback_data="sub:start")],
        [InlineKeyboardButton(text="⭐ Про — 350 (100/день, 30 дней)", callback_data="sub:pro")],
        [InlineKeyboardButton(text="⭐ Премиум — 700 (200/день, 30 дней)", callback_data="sub:premium")],
    ])

def topup_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ +10 запросов — 99⭐", callback_data="topup:10")],
        [InlineKeyboardButton(text="➕ +50 запросов — 150⭐", callback_data="topup:50")],
    ])
