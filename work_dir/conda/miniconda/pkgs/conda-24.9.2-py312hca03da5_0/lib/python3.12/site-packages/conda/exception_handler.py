# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Error handling and error reporting."""

import os
import sys
from functools import lru_cache, partial
from logging import getLogger

from .common.compat import ensure_text_type, on_win

log = getLogger(__name__)


class ExceptionHandler:
    def __call__(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            _, exc_val, exc_tb = sys.exc_info()
            return self.handle_exception(exc_val, exc_tb)

    def write_out(self, *content):
        from logging import getLogger

        from .cli.main import init_loggers

        init_loggers()
        getLogger("conda.stderr").info("\n".join(content))

    @property
    def http_timeout(self):
        from .base.context import context

        return context.remote_connect_timeout_secs, context.remote_read_timeout_secs

    @property
    def user_agent(self):
        from .base.context import context

        return context.user_agent

    @property
    def error_upload_url(self):
        from .base.context import context

        return context.error_upload_url

    def handle_exception(self, exc_val, exc_tb):
        from errno import ENOSPC

        from .exceptions import (
            CondaError,
            CondaMemoryError,
            NoSpaceLeftError,
        )

        if isinstance(exc_val, CondaError):
            if exc_val.reportable:
                return self.handle_reportable_application_exception(exc_val, exc_tb)
            else:
                return self.handle_application_exception(exc_val, exc_tb)
        if isinstance(exc_val, EnvironmentError):
            if getattr(exc_val, "errno", None) == ENOSPC:
                return self.handle_application_exception(
                    NoSpaceLeftError(exc_val), exc_tb
                )
        if isinstance(exc_val, MemoryError):
            return self.handle_application_exception(CondaMemoryError(exc_val), exc_tb)
        if isinstance(exc_val, KeyboardInterrupt):
            self._print_conda_exception(CondaError("KeyboardInterrupt"), exc_tb)
            return 1
        if isinstance(exc_val, SystemExit):
            return exc_val.code
        return self.handle_unexpected_exception(exc_val, exc_tb)

    def handle_application_exception(self, exc_val, exc_tb):
        self._print_conda_exception(exc_val, exc_tb)
        return exc_val.return_code

    def _print_conda_exception(self, exc_val, exc_tb):
        from .exceptions import print_conda_exception

        print_conda_exception(exc_val, exc_tb)

    def handle_unexpected_exception(self, exc_val, exc_tb):
        error_report = self.get_error_report(exc_val, exc_tb)
        self.print_unexpected_error_report(error_report)
        self._upload(error_report)
        rc = getattr(exc_val, "return_code", None)
        return rc if rc is not None else 1

    def handle_reportable_application_exception(self, exc_val, exc_tb):
        error_report = self.get_error_report(exc_val, exc_tb)
        from .base.context import context

        if context.json:
            error_report.update(exc_val.dump_map())
        self.print_expected_error_report(error_report)
        self._upload(error_report)
        return exc_val.return_code

    def get_error_report(self, exc_val, exc_tb):
        from .exceptions import CondaError, _format_exc

        command = " ".join(ensure_text_type(s) for s in sys.argv)
        info_dict = {}
        if " info" not in command:
            # get info_dict, but if we get an exception here too, record it without trampling
            # the original exception
            try:
                from .cli.main_info import get_info_dict

                info_dict = get_info_dict()
            except Exception as info_e:
                info_traceback = _format_exc()
                info_dict = {
                    "error": repr(info_e),
                    "exception_name": info_e.__class__.__name__,
                    "exception_type": str(exc_val.__class__),
                    "traceback": info_traceback,
                }

        error_report = {
            "error": repr(exc_val),
            "exception_name": exc_val.__class__.__name__,
            "exception_type": str(exc_val.__class__),
            "command": command,
            "traceback": _format_exc(exc_val, exc_tb),
            "conda_info": info_dict,
        }

        if isinstance(exc_val, CondaError):
            error_report["conda_error_components"] = exc_val.dump_map()

        return error_report

    def print_unexpected_error_report(self, error_report):
        from .base.context import context

        if context.json:
            from .cli.common import stdout_json

            stdout_json(error_report)
        else:
            message_builder = []
            message_builder.append("")
            message_builder.append(
                "# >>>>>>>>>>>>>>>>>>>>>> ERROR REPORT <<<<<<<<<<<<<<<<<<<<<<"
            )
            message_builder.append("")
            message_builder.extend(
                "    " + line for line in error_report["traceback"].splitlines()
            )
            message_builder.append("")
            message_builder.append("`$ {}`".format(error_report["command"]))
            message_builder.append("")
            if error_report["conda_info"]:
                from .cli.main_info import get_env_vars_str, get_main_info_str

                try:
                    # TODO: Sanitize env vars to remove secrets (e.g credentials for PROXY)
                    message_builder.append(get_env_vars_str(error_report["conda_info"]))
                    message_builder.append(
                        get_main_info_str(error_report["conda_info"])
                    )
                except Exception as e:
                    log.warning("%r", e, exc_info=True)
                    message_builder.append("conda info could not be constructed.")
                    message_builder.append(f"{e!r}")
            message_builder.extend(
                [
                    "",
                    "An unexpected error has occurred. Conda has prepared the above report."
                    "",
                    "If you suspect this error is being caused by a malfunctioning plugin,",
                    "consider using the --no-plugins option to turn off plugins.",
                    "",
                    "Example: conda --no-plugins install <package>",
                    "",
                    "Alternatively, you can set the CONDA_NO_PLUGINS environment variable on",
                    "the command line to run the command without plugins enabled.",
                    "",
                    "Example: CONDA_NO_PLUGINS=true conda install <package>",
                    "",
                ]
            )
            self.write_out(*message_builder)

    def print_expected_error_report(self, error_report):
        from .base.context import context

        if context.json:
            from .cli.common import stdout_json

            stdout_json(error_report)
        else:
            message_builder = []
            message_builder.append("")
            message_builder.append(
                "# >>>>>>>>>>>>>>>>>>>>>> ERROR REPORT <<<<<<<<<<<<<<<<<<<<<<"
            )
            message_builder.append("")
            message_builder.append("`$ {}`".format(error_report["command"]))
            message_builder.append("")
            if error_report["conda_info"]:
                from .cli.main_info import get_env_vars_str, get_main_info_str

                try:
                    # TODO: Sanitize env vars to remove secrets (e.g credentials for PROXY)
                    message_builder.append(get_env_vars_str(error_report["conda_info"]))
                    message_builder.append(
                        get_main_info_str(error_report["conda_info"])
                    )
                except Exception as e:
                    log.warning("%r", e, exc_info=True)
                    message_builder.append("conda info could not be constructed.")
                    message_builder.append(f"{e!r}")
            message_builder.append("")
            message_builder.append(
                "V V V V V V V V V V V V V V V V V V V V V V V V V V V V V V V"
            )
            message_builder.append("")

            message_builder.extend(error_report["error"].splitlines())
            message_builder.append("")

            message_builder.append(
                "A reportable application error has occurred. Conda has prepared the above report."
            )
            message_builder.append("")
            self.write_out(*message_builder)

    # FUTURE: Python 3.8+, replace with functools.cached_property
    @property
    @lru_cache(maxsize=None)
    def _isatty(self):
        try:
            return os.isatty(0) or on_win
        except Exception as e:
            log.debug("%r", e)
            return True

    def _upload(self, error_report) -> None:
        """Determine whether or not to upload the error report."""
        from .base.context import context

        post_upload = False
        if context.report_errors is False:
            # no prompt and no submission
            do_upload = False
        elif context.report_errors is True or context.always_yes:
            # no prompt and submit
            do_upload = True
        elif context.json or context.quiet or not self._isatty:
            # never prompt under these conditions, submit iff always_yes
            do_upload = bool(not context.offline and context.always_yes)
        else:
            # prompt whether to submit
            do_upload = self._ask_upload()
            post_upload = True

        # the upload state is one of the following:
        #   - True: upload error report
        #   - False: do not upload error report
        #   - None: while prompting a timeout occurred

        if do_upload:
            # user wants report to be submitted
            self._execute_upload(error_report)

        if post_upload:
            # post submission text
            self._post_upload(do_upload)

    def _ask_upload(self):
        from .auxlib.type_coercion import boolify
        from .common.io import timeout

        try:
            do_upload = timeout(
                40,
                partial(
                    input,
                    "If submitted, this report will be used by core maintainers to improve\n"
                    "future releases of conda.\n"
                    "Would you like conda to send this report to the core maintainers? "
                    "[y/N]: ",
                ),
            )
            return do_upload and boolify(do_upload)
        except Exception as e:
            log.debug("%r", e)
            return False

    def _execute_upload(self, error_report):
        import getpass
        import json

        from .auxlib.entity import EntityEncoder

        headers = {
            "User-Agent": self.user_agent,
        }
        _timeout = self.http_timeout
        username = getpass.getuser()
        error_report["is_ascii"] = (
            True if all(ord(c) < 128 for c in username) else False
        )
        error_report["has_spaces"] = True if " " in str(username) else False
        data = json.dumps(error_report, sort_keys=True, cls=EntityEncoder) + "\n"
        data = data.replace(str(username), "USERNAME_REMOVED")
        response = None
        try:
            # requests does not follow HTTP standards for redirects of non-GET methods
            # That is, when following a 301 or 302, it turns a POST into a GET.
            # And no way to disable.  WTF
            import requests

            redirect_counter = 0
            url = self.error_upload_url
            response = requests.post(
                url, headers=headers, timeout=_timeout, data=data, allow_redirects=False
            )
            response.raise_for_status()
            while response.status_code in (301, 302) and response.headers.get(
                "Location"
            ):
                url = response.headers["Location"]
                response = requests.post(
                    url,
                    headers=headers,
                    timeout=_timeout,
                    data=data,
                    allow_redirects=False,
                )
                response.raise_for_status()
                redirect_counter += 1
                if redirect_counter > 15:
                    from . import CondaError

                    raise CondaError("Redirect limit exceeded")
            log.debug("upload response status: %s", response and response.status_code)
        except Exception as e:  # pragma: no cover
            log.info("%r", e)
        try:
            if response and response.ok:
                self.write_out("Upload successful.")
            else:
                self.write_out("Upload did not complete.")
                if response and response.status_code:
                    self.write_out(f" HTTP {response.status_code}")
        except Exception as e:
            log.debug(f"{e!r}")

    def _post_upload(self, do_upload):
        if do_upload is True:
            # report was submitted
            self.write_out(
                "",
                "Thank you for helping to improve conda.",
                "Opt-in to always sending reports (and not see this message again)",
                "by running",
                "",
                "    $ conda config --set report_errors true",
                "",
            )
        elif do_upload is None:
            # timeout was reached while prompting user
            self.write_out(
                "",
                "Timeout reached. No report sent.",
                "",
            )
        else:
            # no report submitted
            self.write_out(
                "",
                "No report sent. To permanently opt-out, use",
                "",
                "    $ conda config --set report_errors false",
                "",
            )


def conda_exception_handler(func, *args, **kwargs):
    exception_handler = ExceptionHandler()
    return_value = exception_handler(func, *args, **kwargs)
    return return_value
