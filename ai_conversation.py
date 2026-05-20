"""AI Conversation handler for Discord bot using NVIDIA API."""

import asyncio
import os
import logging
import time
import random
from typing import Dict, List
from openai import AsyncOpenAI
from rate_limiter import get_limiter_from_env

logger = logging.getLogger("red.cogfaithup.ai_conversation")


class AIConversationHandler:
    """Handles AI conversations with users using NVIDIA API."""

    def __init__(self):
        self._client = None
        self.model = "deepseek-ai/deepseek-v3.2"
        # user_id -> (last_access_time, message history)
        self.conversations: Dict[int, List[Dict[str, str]]] = {}
        self._last_access: Dict[int, float] = {}  # user_id -> timestamp
        self.max_conversations = 1000
        self.conversation_ttl = 3600  # 1 hour in seconds
        self._conversations_lock = asyncio.Lock()
        # Rate limiter for NVIDIA API calls
        self._rate_limiter = get_limiter_from_env(
            "NVIDIA", default_max_calls=10, default_period=60
        )

    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            api_key = os.getenv("NVIDIA_API_KEY")
            if not api_key:
                raise ValueError("NVIDIA_API_KEY environment variable is not set")
            self._client = AsyncOpenAI(
                base_url="https://integrate.api.nvidia.com/v1", api_key=api_key
            )
        return self._client

    async def _get_conversation_history(self, user_id: int) -> List[Dict[str, str]]:
        """Get or create conversation history for a user."""
        async with self._conversations_lock:
            now = time.time()
            # Clean up expired conversations first
            expired = [
                uid
                for uid, last in self._last_access.items()
                if now - last > self.conversation_ttl
            ]
            for uid in expired:
                del self.conversations[uid]
                del self._last_access[uid]
                logger.debug("Removed expired conversation for user %s", uid)

            if user_id not in self.conversations:
                # Enforce maximum conversation limit using uniform random
                # selection
                if len(self.conversations) >= self.max_conversations:
                    # Select a random user uniformly
                    random_user = random.choice(list(self.conversations.keys()))
                    del self.conversations[random_user]
                    del self._last_access[random_user]
                    logger.warning(
                        "Reached maximum conversations limit (%s), "
                        "removed random conversation for user %s",
                        self.max_conversations,
                        random_user,
                    )
                # Initialize with system message
                system_message = (
                    "You are a helpful AI assistant in a Discord server. "
                    "Be friendly, engaging, and keep responses concise "
                    "but meaningful. You can have conversations about "
                    "various topics but maintain appropriate discord "
                    "server etiquette."
                )
                self.conversations[user_id] = [
                    {"role": "system", "content": system_message}
                ]
            # Update last access time
            self._last_access[user_id] = now
            return self.conversations[user_id]

    def _trim_conversation_history(
        self, history: List[Dict[str, str]], max_messages: int = 10
    ) -> List[Dict[str, str]]:
        """Trim conversation history to maintain context window."""
        if len(history) > max_messages:
            # Keep system message and recent messages
            return [history[0]] + history[-(max_messages - 1) :]
        return history

    async def generate_response(
        self, user_id: int, user_message: str, message_context=None
    ) -> str:
        """Generate AI response for a user's message."""
        try:
            conversation_history = await self._get_conversation_history(user_id)

            # Add user message to conversation history
            conversation_history.append({"role": "user", "content": user_message})

            # Trim history if needed
            conversation_history = self._trim_conversation_history(conversation_history)

            # Apply rate limiting
            await self._rate_limiter.acquire()
            # Generate response
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=conversation_history,
                temperature=0.2,
                top_p=0.7,
                max_tokens=1024,
                extra_body={"chat_template_kwargs": {"thinking": True}},
                stream=False,  # Use non-streaming for simplicity
            )

            ai_response = completion.choices[0].message.content

            # Add AI response to history
            conversation_history.append({"role": "assistant", "content": ai_response})

            # Update conversation history (already referenced, but ensure)
            async with self._conversations_lock:
                self.conversations[user_id] = conversation_history
                # Update last access time after interaction
                self._last_access[user_id] = time.time()

            return ai_response

        except Exception as e:
            logger.error("Error generating AI response for user %s: %s", user_id, e)
            return (
                "Sorry, I'm having trouble processing your message right now. "
                "Please try again later."
            )

    async def clear_conversation(self, user_id: int) -> bool:
        """Clear conversation history for a user."""
        async with self._conversations_lock:
            if user_id in self.conversations:
                del self.conversations[user_id]
                if user_id in self._last_access:
                    del self._last_access[user_id]
                return True
        return False

    async def get_conversation_count(self) -> int:
        """Get number of active conversations."""
        async with self._conversations_lock:
            return len(self.conversations)


# Global instance
ai_handler = AIConversationHandler()
