from datetime import datetime
import pytz  # type: ignore

from python.helpers.print_style import PrintStyle
from python.helpers.dotenv import get_dotenv_value, save_dotenv_value


class Localization:
    """
    Localization class for handling timezone conversions between UTC and local time.
    """

    # singleton
    _instance = None

    @classmethod
    def get(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = cls(*args, **kwargs)
        return cls._instance

    def __init__(self, timezone: str | None = None):
        if timezone is not None:
            self.set_timezone(timezone)  # Use the setter to validate
        else:
            timezone = str(get_dotenv_value("DEFAULT_USER_TIMEZONE", "UTC"))
            self.set_timezone(timezone)

    def get_timezone(self) -> str:
        return self.timezone

    def set_timezone(self, timezone: str) -> None:
        """Set the timezone, with validation."""
        # Validate timezone
        try:
            pytz.timezone(timezone)
            if timezone != getattr(self, 'timezone', None):
                PrintStyle.debug(f"Changing timezone from {getattr(self, 'timezone', 'None')} to {timezone}")
                self.timezone = timezone
                save_dotenv_value("DEFAULT_USER_TIMEZONE", timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            PrintStyle.error(f"Unknown timezone: {timezone}, defaulting to UTC")
            self.timezone = "UTC"
            # save the default timezone to the environment variable to avoid future errors on startup
            save_dotenv_value("DEFAULT_USER_TIMEZONE", "UTC")

    def localtime_str_to_utc_dt(self, localtime_str: str | None) -> datetime | None:
        """
        Convert a local time ISO string to a UTC datetime object.
        Returns None if input is None or invalid.
        """
        if not localtime_str:
            return None

        try:
            # Handle both with and without timezone info
            try:
                # Try parsing with timezone info first
                local_datetime_obj = datetime.fromisoformat(localtime_str)
                if local_datetime_obj.tzinfo is None:
                    # If no timezone info, assume it's in the configured timezone
                    local_datetime_obj = pytz.timezone(self.timezone).localize(local_datetime_obj)
            except ValueError:
                # If timezone parsing fails, try without timezone
                local_datetime_obj = datetime.fromisoformat(localtime_str.split('Z')[0].split('+')[0])
                local_datetime_obj = pytz.timezone(self.timezone).localize(local_datetime_obj)

            # Convert to UTC
            return local_datetime_obj.astimezone(pytz.utc)
        except Exception as e:
            PrintStyle.error(f"Error converting localtime string to UTC: {e}")
            return None

    def utc_dt_to_localtime_str(self, utc_dt: datetime | None, sep: str = "T", timespec: str = "auto") -> str | None:
        """
        Convert a UTC datetime object to a local time ISO string.
        Returns None if input is None.
        """
        if utc_dt is None:
            return None

        # At this point, utc_dt is definitely not None
        assert utc_dt is not None

        try:
            # Ensure datetime is timezone aware
            if utc_dt.tzinfo is None:
                utc_dt = pytz.utc.localize(utc_dt)
            elif utc_dt.tzinfo != pytz.utc:
                utc_dt = utc_dt.astimezone(pytz.utc)

            # Convert to local time
            local_datetime_obj = utc_dt.astimezone(pytz.timezone(self.timezone))
            # Return the local time string
            return local_datetime_obj.isoformat(sep=sep, timespec=timespec)
        except Exception as e:
            PrintStyle.error(f"Error converting UTC datetime to localtime string: {e}")
            return None

    def serialize_datetime(self, dt: datetime | None) -> str | None:
        """
        Serialize a datetime object to ISO format string in the user's timezone.
        This ensures the frontend receives dates in the correct timezone for display.
        """
        if dt is None:
            return None

        # At this point, dt is definitely not None
        assert dt is not None

        try:
            # Ensure datetime is timezone aware (if not, assume UTC)
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)

            # Convert to the user's timezone
            local_timezone = pytz.timezone(self.timezone)
            local_dt = dt.astimezone(local_timezone)

            return local_dt.isoformat()
        except Exception as e:
            PrintStyle.error(f"Error serializing datetime: {e}")
            return None
