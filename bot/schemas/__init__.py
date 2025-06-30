"""
Structured output schemas for the AI Telegram bot.
"""
from .response_schemas import (
    RESPONSE_SCHEMAS,
    get_response_schema,
    detect_response_type,
    RESPONSE_TYPE_DESCRIPTIONS,
    ChatResponse,
    CodeResponse,
    AnalysisResponse,
    MathResponse,
    HelpResponse,
    ErrorResponse,
    ImageAnalysisResponse,
    RefusalResponse
)

__all__ = [
    'RESPONSE_SCHEMAS',
    'get_response_schema', 
    'detect_response_type',
    'RESPONSE_TYPE_DESCRIPTIONS',
    'ChatResponse',
    'CodeResponse',
    'AnalysisResponse', 
    'MathResponse',
    'HelpResponse',
    'ErrorResponse',
    'ImageAnalysisResponse',
    'RefusalResponse'
]