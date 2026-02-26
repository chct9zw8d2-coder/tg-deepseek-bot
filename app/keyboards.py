from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Помощь с дз"), KeyboardButton(text="📷 Загрузить фото и решить дз")],
            [KeyboardButton(text="❓ Ответить на любой вопрос")],
            [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="👥 Реферальная программа")],
            [KeyboardButton(text="➕ Докупить")],
        ],
        resize_keyboard=True
    )

def subscription_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Старт — 199⭐ / 50 в день (30 дней)", callback_data="buy:sub:start")],
        [InlineKeyboardButton(text="Про — 350⭐ / 100 в день (30 дней)", callback_data="buy:sub:pro")],
        [InlineKeyboardButton(text="Премиум — 700⭐ / 200 в день (30 дней)", callback_data="buy:sub:premium")],
    ])

def topup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="+10 запросов — 99⭐", callback_data="buy:topup:10")],
        [InlineKeyboardButton(text="+50 запросов — 150⭐", callback_data="buy:topup:50")],
    ])
