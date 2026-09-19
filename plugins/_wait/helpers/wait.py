import asyncio
from datetime import timedelta

from helpers.localization import Localization
from helpers.print_style import PrintStyle


def format_remaining_time(total_seconds: float) -> str:
    if total_seconds < 0:
        total_seconds = 0

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    days = int(days)
    hours = int(hours)
    minutes = int(minutes)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")

    if days > 0 or hours > 0:
        if seconds >= 1:
            parts.append(f"{int(seconds)}s")
    elif minutes > 0:
        if seconds >= 0.1:
            parts.append(f"{seconds:.1f}s")
    else:
        parts.append(f"{total_seconds:.1f}s")

    if not parts:
        return "0.0s remaining"

    return " ".join(parts) + " remaining"


async def managed_wait(agent, target_time, is_duration_wait, log, get_heading_callback):
    
    # Anchor updates to absolute 1s ticks so per-loop overhead cannot shift the
    # visible countdown phase and make it skip values (5.0, 4.0, 2.9, ...).
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
