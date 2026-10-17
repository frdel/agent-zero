import asyncio
from datetime import timedelta

from helpers.localization import Localization
from helpers.print_style import PrintStyle


def format_remaining_time(total_seconds: float) -> str:
    # Whole seconds only: the wait loop ticks on whole-second boundaries.
    total_seconds = int(max(total_seconds, 0))

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")

    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts) + " remaining"


async def managed_wait(agent, target_time, is_duration_wait, log, get_heading_callback):
    
    # Anchor updates to absolute 1s ticks so overhead cannot shift the countdown phase.
    next_tick = Localization.get().now()

    while Localization.get().now() < target_time:
        before_intervention = Localization.get().now()
        await agent.handle_intervention()
        after_intervention = Localization.get().now()

        if is_duration_wait:
            pause_duration = after_intervention - before_intervention
            if pause_duration.total_seconds() > 1.5:  # Adjust for pauses longer than the sleep cycle
                target_time += pause_duration
                next_tick += pause_duration
                PrintStyle.info(
                    f"Wait extended by {pause_duration.total_seconds():.1f}s to {Localization.get().serialize_datetime(target_time)}...",
                )

        current_time = Localization.get().now()
        if current_time >= target_time:
            break

        remaining_seconds = (target_time - current_time).total_seconds()
        if log:
            log.update(heading=get_heading_callback(format_remaining_time(remaining_seconds)))

        next_tick += timedelta(seconds=1.0)
        if next_tick <= current_time:
            next_tick = current_time
        sleep_duration = min((next_tick - current_time).total_seconds(), remaining_seconds)

        await asyncio.sleep(max(sleep_duration, 0.0))

    return target_time
