"""
Structured output schemas for AI responses to ensure reliable parsing and validation.
"""
from typing import Dict, Any, Literal, Optional
from pydantic import BaseModel, Field


class BaseAIResponse(BaseModel):
    """Base class for all AI responses with common fields."""
    
    content: str = Field(description="The main response content")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence in the response (0-1)")
    language: str = Field(default="en", description="Language of the response")


class ChatResponse(BaseAIResponse):
    """Standard chat response for general conversations."""
    
    response_type: Literal["chat"] = "chat"
    intent: str = Field(description="Detected user intent or topic")
    requires_followup: bool = Field(default=False, description="Whether the response needs follow-up")
    context_used: bool = Field(default=False, description="Whether chat history was used")


class CodeResponse(BaseAIResponse):
    """Response containing code with metadata."""
    
    response_type: Literal["code"] = "code"
    programming_language: str = Field(description="Programming language of the code")
    code_type: Literal["snippet", "function", "class", "script", "example"] = Field(
        description="Type of code provided"
    )
    explanation: str = Field(description="Explanation of what the code does")
    requires_testing: bool = Field(default=True, description="Whether code should be tested")


class AnalysisResponse(BaseAIResponse):
    """Response for analytical tasks like data analysis or explanation."""
    
    response_type: Literal["analysis"] = "analysis"
    analysis_type: Literal["data", "text", "image", "comparison", "explanation"] = Field(
        description="Type of analysis performed"
    )
    key_findings: list[str] = Field(description="Key findings or insights")
    methodology: Optional[str] = Field(default=None, description="Analysis approach used")
    limitations: Optional[str] = Field(default=None, description="Limitations of the analysis")


class MathResponse(BaseAIResponse):
    """Response for mathematical problems and calculations."""
    
    response_type: Literal["math"] = "math"
    problem_type: Literal["calculation", "proof", "explanation", "word_problem", "formula"] = Field(
        description="Type of mathematical problem"
    )
    steps: list[str] = Field(description="Step-by-step solution process")
    final_answer: str = Field(description="Final numerical or algebraic answer")
    units: Optional[str] = Field(default=None, description="Units of the answer if applicable")


class HelpResponse(BaseAIResponse):
    """Response for help requests and instructions."""
    
    response_type: Literal["help"] = "help"
    help_category: Literal["bot_usage", "technical", "general", "troubleshooting"] = Field(
        description="Category of help requested"
    )
    instructions: list[str] = Field(description="Step-by-step instructions")
    related_commands: list[str] = Field(default_factory=list, description="Related bot commands")


class ErrorResponse(BaseAIResponse):
    """Response for error handling and clarification requests."""
    
    response_type: Literal["error"] = "error"
    error_type: Literal["unclear_request", "unsupported_task", "content_filter", "rate_limit"] = Field(
        description="Type of error encountered"
    )
    suggestion: str = Field(description="Suggested next action for the user")
    can_retry: bool = Field(default=True, description="Whether user can retry the request")


class ImageAnalysisResponse(BaseAIResponse):
    """Response for image analysis tasks."""
    
    response_type: Literal["image_analysis"] = "image_analysis"
    objects_detected: list[str] = Field(default_factory=list, description="Objects or elements detected")
    scene_description: str = Field(description="Overall scene description")
    text_content: Optional[str] = Field(default=None, description="Any text found in the image")
    analysis_confidence: float = Field(ge=0.0, le=1.0, description="Confidence in image analysis")


class RefusalResponse(BaseAIResponse):
    """Response when the AI needs to refuse a request."""
    
    response_type: Literal["refusal"] = "refusal"
    refusal_reason: Literal["safety", "policy", "capability", "inappropriate"] = Field(
        description="Reason for refusal"
    )
    alternative_suggestion: Optional[str] = Field(
        default=None, 
        description="Alternative approach the user could try"
    )


# Schema mapping for different response types
RESPONSE_SCHEMAS = {
    "chat": ChatResponse.model_json_schema(),
    "code": CodeResponse.model_json_schema(),
    "analysis": AnalysisResponse.model_json_schema(),
    "math": MathResponse.model_json_schema(),
    "help": HelpResponse.model_json_schema(),
    "error": ErrorResponse.model_json_schema(),
    "image_analysis": ImageAnalysisResponse.model_json_schema(),
    "refusal": RefusalResponse.model_json_schema(),
}


def get_response_schema(response_type: str) -> Dict[str, Any]:
    """
    Get the JSON schema for a specific response type.
    
    Args:
        response_type: Type of response (chat, code, analysis, etc.)
        
    Returns:
        JSON schema dict for the response type
        
    Raises:
        ValueError: If response_type is not supported
    """
    if response_type not in RESPONSE_SCHEMAS:
        raise ValueError(f"Unsupported response type: {response_type}")
    
    return RESPONSE_SCHEMAS[response_type]


def detect_response_type(user_message: str, has_image: bool = False) -> str:
    """
    Detect the most appropriate response type based on user input.
    
    Args:
        user_message: The user's message text
        has_image: Whether the message contains an image
        
    Returns:
        Appropriate response type for structured output
    """
    message_lower = user_message.lower().strip()
    
    # Image analysis
    if has_image:
        return "image_analysis"
    
    # Help requests
    if any(keyword in message_lower for keyword in ["help", "how to", "tutorial", "guide", "explain how"]):
        return "help"
    
    # Math problems
    if any(keyword in message_lower for keyword in ["calculate", "solve", "math", "equation", "formula", "+", "-", "*", "/", "="]):
        return "math"
    
    # Code requests
    if any(keyword in message_lower for keyword in ["code", "program", "script", "function", "class", "def ", "python", "javascript", "java", "c++", "html", "css"]):
        return "code"
    
    # Analysis requests
    if any(keyword in message_lower for keyword in ["analyze", "analysis", "compare", "explain", "breakdown", "summarize", "evaluate"]):
        return "analysis"
    
    # Default to chat
    return "chat"


# Response type descriptions for the AI model
RESPONSE_TYPE_DESCRIPTIONS = {
    "chat": "General conversation and questions",
    "code": "Programming and coding requests",
    "analysis": "Analysis, explanation, and comparison tasks",
    "math": "Mathematical problems and calculations",
    "help": "Help requests and instructions",
    "error": "Error handling and clarification",
    "image_analysis": "Image analysis and description",
    "refusal": "When request must be refused"
}