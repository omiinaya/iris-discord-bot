"""Daily Announcements Cog for Discord bot using discord.ext.tasks."""

import logging
import discord
from datetime import datetime
from typing import Dict
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from discord.ext import tasks

logger = logging.getLogger("red.cogfaithup.announcements")


class AnnouncementsCog(commands.Cog):
    """Cog for managing daily scheduled announcements."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1234567890, force_registration=True
        )

        # Default configuration
        default_global = {"announcements": [], "enabled": True, "default_channel": None}

        self.config.register_global(**default_global)

        # Start the scheduler
        self.announcement_task.start()
        logger.info("AnnouncementsCog loaded and initialized.")

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.announcement_task.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the cog is ready."""
        logger.info("AnnouncementsCog ready and listening for announcements.")

    @commands.group(name="announcement", aliases=["announce"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def announcement_group(self, ctx: commands.Context):
        """Manage daily announcements."""
        if not ctx.invoked_subcommand:
            await ctx.send_help()

    @announcement_group.command(name="add")
    async def announcement_add(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        time_str: str,
        *,
        message: str,
    ):
        """Add a daily announcement."""
        try:
            # Parse time
            hour, minute = map(int, time_str.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                await ctx.send("Invalid time format. Use HH:MM (24-hour).")
                return

            async with self.config.announcements() as announcements:
                announcement_id = len(announcements) + 1
                new_announcement = {
                    "id": announcement_id,
                    "guild_id": ctx.guild.id,
                    "channel_id": channel.id,
                    "time": {"hour": hour, "minute": minute},
                    "message": message,
                    "enabled": True,
                }
                announcements.append(new_announcement)

            await ctx.send(
                f"✅ Announcement #{announcement_id} added!\n"
                f"**Channel:** {channel.mention}\n"
                f"**Time:** {time_str}\n"
                f"**Message:** {message}"
            )

        except ValueError:
            await ctx.send("Invalid time format. Use HH:MM (24-hour).")
        except Exception as e:
            logger.error("Error adding announcement: %s", e)
            await ctx.send("Error adding announcement.")

    @announcement_group.command(name="list")
    async def announcement_list(self, ctx: commands.Context):
        """List all announcements for this server."""
        announcements = await self.config.announcements()
        guild_announcements = [
            ann for ann in announcements if ann.get("guild_id") == ctx.guild.id
        ]

        if not guild_announcements:
            await ctx.send("No announcements configured for this server.")
            return

        embed = discord.Embed(title="📢 Server Announcements", color=0x00FF00)

        for ann in guild_announcements:
            channel = self.bot.get_channel(ann["channel_id"])
            channel_name = channel.mention if channel else "Unknown Channel"
            time_str = f"{ann['time']['hour']:02d}:{ann['time']['minute']:02d}"
            status = "✅ Enabled" if ann.get("enabled", True) else "❌ Disabled"
            msg_preview = ann["message"][:100]
            if len(ann["message"]) > 100:
                msg_preview += "..."

            embed.add_field(
                name=f"Announcement #{ann['id']}",
                value=(
                    f"**Channel:** {channel_name}\n"
                    f"**Time:** {time_str}\n"
                    f"**Status:** {status}\n"
                    f"**Message:** {msg_preview}"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    @announcement_group.command(name="remove")
    async def announcement_remove(self, ctx: commands.Context, announcement_id: int):
        """Remove an announcement by its ID."""
        async with self.config.announcements() as announcements:
            for i, ann in enumerate(announcements):
                if ann["id"] == announcement_id and ann.get("guild_id") == ctx.guild.id:
                    del announcements[i]
                    await ctx.send(f"✅ Announcement #{announcement_id} removed.")
                    return

        await ctx.send(f"❌ Announcement #{announcement_id} not found.")

    @announcement_group.command(name="enable")
    async def announcement_enable(self, ctx: commands.Context, announcement_id: int):
        """Enable a disabled announcement."""
        async with self.config.announcements() as announcements:
            for ann in announcements:
                if ann["id"] == announcement_id and ann.get("guild_id") == ctx.guild.id:
                    ann["enabled"] = True
                    await ctx.send(f"✅ Announcement #{announcement_id} enabled.")
                    return

        await ctx.send(f"❌ Announcement #{announcement_id} not found.")

    @announcement_group.command(name="disable")
    async def announcement_disable(self, ctx: commands.Context, announcement_id: int):
        """Disable an announcement."""
        async with self.config.announcements() as announcements:
            for ann in announcements:
                if ann["id"] == announcement_id and ann.get("guild_id") == ctx.guild.id:
                    ann["enabled"] = False
                    await ctx.send(f"✅ Announcement #{announcement_id} disabled.")
                    return

        await ctx.send(f"❌ Announcement #{announcement_id} not found.")

    @announcement_group.command(name="test")
    async def announcement_test(self, ctx: commands.Context, announcement_id: int):
        """Test an announcement by sending it immediately."""
        announcements = await self.config.announcements()
        announcement = None

        for ann in announcements:
            if ann["id"] == announcement_id and ann.get("guild_id") == ctx.guild.id:
                announcement = ann
                break

        if not announcement:
            await ctx.send(f"❌ Announcement #{announcement_id} not found.")
            return

        if not announcement.get("enabled", True):
            await ctx.send("❌ This announcement is disabled. Enable it first.")
            return

        channel = self.bot.get_channel(announcement["channel_id"])
        if not channel:
            await ctx.send("❌ Announcement channel not found.")
            return

        # Send the test announcement
        try:
            await channel.send(announcement["message"])
            await ctx.send(f"✅ Test announcement sent to {channel.mention}")
        except discord.Forbidden:
            await ctx.send("❌ No permission to send messages in that channel.")
        except Exception as e:
            logger.error("Error testing announcement: %s", e)
            await ctx.send("❌ Error sending test announcement.")

    @tasks.loop(minutes=1.0)
    async def announcement_task(self):
        """Check every minute if it's time to send any announcements."""
        if not await self.config.enabled():
            return

        announcements = await self.config.announcements()
        if not announcements:
            return

        current_time = datetime.now().time()
        current_hour = current_time.hour
        current_minute = current_time.minute

        for announcement in announcements:
            # Skip disabled announcements
            if not announcement.get("enabled", True):
                continue

            # Check if it's time for this announcement
            if (
                announcement["time"]["hour"] == current_hour
                and announcement["time"]["minute"] == current_minute
            ):
                await self._send_announcement(announcement)

    async def _send_announcement(self, announcement: Dict):
        """Send an announcement to its designated channel."""
        try:
            channel = self.bot.get_channel(announcement["channel_id"])
            if not channel:
                logger.warning(
                    "Channel not found for announcement #%s", announcement["id"]
                )
                return

            # Check if we have permission to send messages
            if not channel.permissions_for(channel.guild.me).send_messages:
                logger.warning("No permission to send messages in %s", channel.name)
                return

            await channel.send(announcement["message"])
            logger.info("Sent announcement #%s to %s", announcement["id"], channel.name)

        except discord.Forbidden:
            logger.warning("No permission to send messages in channel")
        except Exception as e:
            logger.error("Error sending announcement #%s: %s", announcement["id"], e)

    @announcement_task.before_loop
    async def before_announcement_task(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()


async def setup(bot: Red):
    """Setup function to add the cog to the bot."""
    cog = AnnouncementsCog(bot)
    await bot.add_cog(cog)
    logger.info("AnnouncementsCog setup completed.")
