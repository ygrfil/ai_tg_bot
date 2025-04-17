from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    chatting = State()
    choosing_provider = State()
    admin_menu = State()
    broadcasting = State()
    waiting_for_image_prompt = State()  # New state for image generation 