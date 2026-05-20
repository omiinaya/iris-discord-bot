from typing import Optional, Tuple
from redbot.core import commands


def is_valid_member(ctx: commands.Context, member) -> Tuple[bool, Optional[str]]:
    """Check if the member is not the command author."""
    if member == ctx.author:
        return False, "You can't play against yourself!"
    return True, None
