from __future__ import annotations

from helpers.extension import Extension
from helpers.watchdog import batch_watchdogs
from plugins._time_travel.helpers.time_travel import register_watchdogs


class RegisterTimeTravelWatchdog(Extension):
    def execute(self, **kwargs):
        with batch_watchdogs():
            register_watchdogs()
