from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    """State machine for user interaction flow."""
    IDLE = State()
    AWAITING_MODEL_SELECTION = State()
    AWAITING_MESSAGE = State()
    GENERATING_RESPONSE = State()
    AWAITING_IMAGE = State()
    AWAITING_CONFIRMATION = State()
    # States from the second definition
    CHATTING = State()
    CHOOSING_PROVIDER = State()
    ADMIN_MENU = State()
    BROADCASTING = State()
    WAITING_FOR_IMAGE_PROMPT = State()
    
class ConversationState(StatesGroup):
    """State machine for conversation management."""
    ACTIVE = State()
    VIEWING_HISTORY = State()
    CLEARING_HISTORY = State()

class AdminStates(StatesGroup):
    """State machine for admin operations."""
    AWAITING_BROADCAST_MESSAGE = State()
    AWAITING_USER_ID = State()
    CONFIGURING_SYSTEM = State() 