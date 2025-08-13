"""Gemini LLM client implementation."""

import logging
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class GeminiClient:
    """Gemini LLM client wrapper."""
    
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.model_name = model_name
        self.model = ChatGoogleGenerativeAI(model=model_name)
        logger.info(f"Initialized Gemini client with model: {model_name}")
    
    async def generate_title(self, prompt: str) -> str:
        """Generate a title using the LLM."""
        try:
            response = self.model.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error generating title: {e}")
            raise
    
    def bind_tools(self, tools):
        """Bind tools to the model."""
        return self.model.bind_tools(tools)
    
    def get_model(self):
        """Get the underlying model instance."""
        return self.model