"""AI service for processing messages with OpenAI API."""

import asyncio
import logging
import time
from typing import AsyncGenerator, Optional

from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config.settings import config
from src.services.conversation_memory import get_conversation_memory
from src.utils.secure_headers import get_secure_openai_client_kwargs

logger = logging.getLogger(__name__)


class OpenAIServiceError(Exception):
    """Base exception for OpenAI service errors."""
    pass


class TokenUsage:
    """Token usage information from OpenAI API."""

    def __init__(self, prompt_tokens: int, completion_tokens: int, total_tokens: int):
        """
        Initialize token usage.

        Args:
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion
            total_tokens: Total number of tokens used
        """
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens

    def __str__(self) -> str:
        """String representation of token usage."""
        return (
            f"Token Usage - Prompt: {self.prompt_tokens}, "
            f"Completion: {self.completion_tokens}, "
            f"Total: {self.total_tokens}"
        )


class OpenAIService:
    """
    Service for interacting with OpenAI API with streaming and retry logic.
    """

    def __init__(self):
        """Initialize OpenAI service with secure HTTP client defaults."""
        # Use a TLS-verified HTTP client with strict timeouts so the bot
        # never hangs indefinitely if the OpenAI API is slow or unreachable.
        secure_kwargs = get_secure_openai_client_kwargs()
        self.client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=float(config.API_TIMEOUT),
            **secure_kwargs,
        )
        self.model = config.AI_MODEL
        self.conversation_memory = get_conversation_memory()
        self.max_retries = 3
        self.stream_batch_interval = 1.5  # Update message every 1.5 seconds
        self.api_timeout = float(config.API_TIMEOUT)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((OpenAIServiceError, asyncio.TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying OpenAI API call (attempt {retry_state.attempt_number})"
        ),
    )
    async def _call_openai_with_retry(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[tuple[str, Optional[TokenUsage]], None]:
        """
        Call OpenAI API with exponential backoff retry logic.

        Args:
            messages: List of messages in OpenAI chat format

        Yields:
            Tuple of (chunk content, token usage if available)

        Raises:
            OpenAIServiceError: If API call fails after retries
            asyncio.TimeoutError: If the API call exceeds the configured timeout
        """
        try:
            timeout = config.API_TIMEOUT
            async with asyncio.timeout(timeout):
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=2000,
                    timeout=timeout,
                )

                full_response = ""
                token_usage = None

                # IMPORTANT: The timeout MUST also cover the streaming loop,
                # not just the initial request. This ensures the bot never
                # hangs indefinitely if the streaming connection stalls.
                async for chunk in stream:
                    # Extract content
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield content, None

                    # Extract token usage from the last chunk
                    if chunk.usage is not None:
                        token_usage = TokenUsage(
                            prompt_tokens=chunk.usage.prompt_tokens,
                            completion_tokens=chunk.usage.completion_tokens,
                            total_tokens=chunk.usage.total_tokens,
                        )

                # Yield token usage at the end
                if token_usage:
                    yield "", token_usage

        except (asyncio.TimeoutError, TimeoutError) as e:
            logger.error(f"OpenAI API call timed out after {config.API_TIMEOUT}s")
            raise OpenAIServiceError(
                f"OpenAI API call timed out after {config.API_TIMEOUT}s"
            ) from e
        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            raise OpenAIServiceError(f"OpenAI API call failed: {str(e)}") from e

    async def generate_response(
        self, user_id: int, user_message: str
    ) -> tuple[str, Optional[TokenUsage]]:
        """
        Generate AI response for a user message.

        Args:
            user_id: Telegram user ID
            user_message: User's message text

        Returns:
            Tuple of (complete response text, token usage info)
        """
        # Add user message to conversation history
        self.conversation_memory.add_message(user_id, "user", user_message)

        # Get conversation history
        messages = self.conversation_memory.get_history(user_id)

        try:
            # Collect the full response from the stream
            full_response = ""
            token_usage = None

            async for chunk, usage in self._call_openai_with_retry(messages):
                if chunk:
                    full_response += chunk
                if usage:
                    token_usage = usage

            # Add assistant response to conversation history
            self.conversation_memory.add_message(user_id, "assistant", full_response)

            # Log token usage
            if token_usage:
                logger.info(f"Token usage for user {user_id}: {token_usage}")

            return full_response, token_usage

        except OpenAIServiceError as e:
            logger.error(f"Failed to generate response for user {user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating response: {e}", exc_info=True)
            raise OpenAIServiceError(f"Unexpected error: {str(e)}") from e

    async def generate_response_stream(
        self, user_id: int, user_message: str
    ) -> AsyncGenerator[str, None]:
        """
        Generate AI response as a stream for real-time updates.

        Args:
            user_id: Telegram user ID
            user_message: User's message text

        Yields:
            Chunks of the response text
        """
        # Add user message to conversation history
        self.conversation_memory.add_message(user_id, "user", user_message)

        # Get conversation history
        messages = self.conversation_memory.get_history(user_id)

        full_response = ""
        token_usage = None

        try:
            async for chunk, usage in self._call_openai_with_retry(messages):
                if chunk:
                    full_response += chunk
                    yield chunk
                if usage:
                    token_usage = usage

            # Add complete assistant response to conversation history
            self.conversation_memory.add_message(user_id, "assistant", full_response)

            # Log token usage
            if token_usage:
                logger.info(f"Token usage for user {user_id}: {token_usage}")

        except OpenAIServiceError as e:
            logger.error(f"Streaming error for user {user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected streaming error: {e}", exc_info=True)
            raise OpenAIServiceError(f"Unexpected error: {str(e)}") from e

    def clear_user_history(self, user_id: int) -> None:
        """
        Clear conversation history for a user.

        Args:
            user_id: Telegram user ID
        """
        self.conversation_memory.clear_history(user_id)
        logger.info(f"Cleared conversation history for user {user_id}")

    def set_system_prompt(self, user_id: int, prompt: str) -> None:
        """
        Set a custom system prompt for a user.

        Args:
            user_id: Telegram user ID
            prompt: System prompt text
        """
        self.conversation_memory.set_system_prompt(user_id, prompt)
        logger.info(f"Set system prompt for user {user_id}")

    def get_system_prompt(self, user_id: int) -> Optional[str]:
        """
        Get the system prompt for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            System prompt text or None
        """
        return self.conversation_memory.get_system_prompt(user_id)


# Global AI service instance
_ai_service: Optional[OpenAIService] = None


def get_ai_service() -> OpenAIService:
    """
    Get or create the global AI service instance.

    Returns:
        OpenAIService instance
    """
    global _ai_service
    if _ai_service is None:
        _ai_service = OpenAIService()
    return _ai_service
