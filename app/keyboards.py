
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Помощь с дз"), KeyboardButton(text="📷 Загрузить фото и решить дз")],
            [KeyboardButton(text="❓ Ответить на любой вопрос")],
            [KeyboardButton(text="💳 Подписка"), KeyboardButton(text="🎁 Реферальная программа")],
            [KeyboardButton(text="➕ Докупить")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери пункт меню или напиши вопрос…",
    )

def subscription_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    if is_admin:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Вам доступно бесплатно (админ)", callback_data="noop")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Старт — 199⭐ / день (50)", callback_data="buy:sub:starter")],
        [InlineKeyboardButton(text="Про — 350⭐ / день (100)", callback_data="buy:sub:pro")],
        [InlineKeyboardButton(text="Премиум — 700⭐ / день (200)", callback_data="buy:sub:premium")],
    ])

def topup_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    if is_admin:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Вам доступно бесплатно (админ)", callback_data="noop")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="+10 запросов — 99⭐", callback_data="buy:topup:10")],
        [InlineKeyboardButton(text="+50 запросов — 150⭐", callback_data="buy:topup:50")],
    ])

def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="🎁 Выдать кредиты", callback_data="admin:grant")],
    ])
