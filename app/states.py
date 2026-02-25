from aiogram.fsm.state import StatesGroup, State

class Mode(StatesGroup):
    homework = State()
    photo = State()
    any_question = State()
