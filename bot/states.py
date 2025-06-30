from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    """States for user interaction with the bot."""
    chatting = State()         # Default state for general chat
    choosing_provider = State() # State when user is selecting AI provider
    admin_menu = State()       # State for admin menu
    broadcasting = State()     # State for broadcasting messages
    user_management = State()  # State for user management
    settings_menu = State()    # State for bot settings
    waiting_for_image_prompt = State()  # State for waiting for image prompt 