from .mycog import MyCog
from .announcements_cog import AnnouncementsCog


async def setup(bot):
    await bot.add_cog(MyCog(bot))
    await bot.add_cog(AnnouncementsCog(bot))
