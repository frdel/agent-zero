from helpers.api import register_watchdogs as register_api_watchdogs
from helpers.extension import Extension
from helpers.plugins import register_watchdogs as register_plugins_watchdogs
from helpers.watchdog import batch_watchdogs


class RegisterWatchDogs(Extension):

    def execute(self, **kwargs):
        with batch_watchdogs():
            register_plugins_watchdogs()
            register_api_watchdogs()