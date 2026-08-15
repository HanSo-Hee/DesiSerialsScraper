# github.com/MrAbhi2k3

import time
import math
import logging
from pyrogram.types import Message

logger = logging.getLogger(__name__)


def humanbytes(size: float) -> str:
    if not size:
        return "0 B"
    power = 1024
    n = 0
    dic_power_n = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{round(size, 2)} {dic_power_n[n]}"


def time_formatter(seconds: float) -> str:
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        ((str(days) + "d, ") if days else "") +
        ((str(hours) + "h, ") if hours else "") +
        ((str(minutes) + "m, ") if minutes else "") +
        ((str(seconds) + "s") if seconds else "")
    )
    return tmp if tmp else "0s"


class ProgressTracker:
    def __init__(self, message: Message, action_name: str = "Processing"):
        self.message = message
        self.action_name = action_name
        self.start_time = time.time()
        self.last_update_time = time.time()

    async def update(self, current: int, total: int):
        now = time.time()
        diff = now - self.start_time

        if (now - self.last_update_time < 3.5 and current < total) or diff <= 0:
            return

        self.last_update_time = now
        percentage = (current * 100) / total if total > 0 else 0
        speed = current / diff
        time_to_completion = round((total - current) / speed) if speed > 0 else 0

        completed_blocks = math.floor(percentage / 5)
        progress_bar = "".join(["▣" for _ in range(completed_blocks)]) + "".join(["▢" for _ in range(20 - completed_blocks)])

        eta_str = time_formatter(time_to_completion)
        speed_str = f"{humanbytes(speed)}/s"
        current_str = humanbytes(current)
        total_str = humanbytes(total)

        text = (
            f"🔄 **{self.action_name}...**\n\n"
            f"[{progress_bar}] **{round(percentage, 2)}%**\n\n"
            f"• **Done:** `{current_str}` of `{total_str}`\n"
            f"• **Speed:** `{speed_str}`\n"
            f"• **ETA:** `{eta_str}`"
        )

        try:
            await self.message.edit_text(text)
        except Exception as e:
            logger.debug(f"Progress edit skipped: {e}")
