
from aiogram.fsm.state import StatesGroup, State

class Mode(StatesGroup):
    idle = State()
    homework_text = State()
    any_question = State()
    photo_homework = State()
