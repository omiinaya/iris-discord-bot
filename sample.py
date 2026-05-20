import os
from dotenv import load_dotenv
from redbot.core import commands
import logging
from typing import Optional

from async_http_client import aget

# Load environment variables from .env file
load_dotenv()
logger = logging.getLogger("red.cogfaithup.sample")


class MyCog(commands.Cog):
    """My custom cog for sample commands and listeners."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mycom(self, ctx: commands.Context) -> None:
        """Responds with a test message."""
        await ctx.send("I can do stuff!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if self.bot.user.mentioned_in(message) and not message.author.bot:
            await message.channel.send("Hello, this is a test response.")

    @commands.command()
    async def apicall(self, ctx: commands.Context, url: Optional[str] = None) -> None:
        """Makes an API call and returns the response. Optionally takes a URL argument."""
        api_url = url or os.getenv("SAMPLE_API")
        if not api_url or not api_url.startswith(("http://", "https://")):
            await ctx.send(
                "API URL not configured or invalid. Please set SAMPLE_API in your .env file or provide a valid URL."
            )
            return
        try:
            response = await aget(api_url, timeout=10)
            logger.info(
                "API call to %s returned status %s", api_url, response.status_code
            )
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    data = response.json()
                    message = f"API Response: {data}"
                else:
                    data = response.text
                    message = f"API Response: {data}"
                # Truncate long responses for accessibility
                if len(message) > 1800:
                    message = message[:1800] + "... (truncated)"
                await ctx.send(message)
            else:
                await ctx.send(
                    f"Failed to retrieve data from the API. Status: {response.status_code}"
                )
        except Exception as e:
            logger.error("API call failed: %s", e)
            await ctx.send(f"API call failed: {e}")


def setup(bot):
    bot.add_cog(MyCog(bot))
