from collections.abc import Callable
from datetime import datetime, tzinfo
from typing import Any

from .conf import Settings, apply_settings
from .timezone_parser import pop_tz_offset_from_string
from .utils import _get_localzone, apply_timezone, localize_timezone, strip_braces


def _apply_timezone_settings(
    date_obj: datetime, ptz: tzinfo | None, settings: Settings
) -> datetime:
    """Return *date_obj*, read from a date string with the time zone *ptz*,
    if any, in the time zone that *settings* ask for."""
    _settings_tz = settings.TIMEZONE.lower()

    if ptz:
        if hasattr(ptz, "localize"):
            date_obj = ptz.localize(date_obj)
        else:
            date_obj = date_obj.replace(tzinfo=ptz)
        if "local" not in _settings_tz:
            date_obj = apply_timezone(date_obj, settings.TIMEZONE)
    elif "local" in _settings_tz:
        date_obj = date_obj.replace(tzinfo=_get_localzone())
    else:
        date_obj = localize_timezone(date_obj, settings.TIMEZONE)

    if settings.TO_TIMEZONE:
        date_obj = apply_timezone(date_obj, settings.TO_TIMEZONE)

    if not settings.RETURN_AS_TIMEZONE_AWARE or (
        settings.RETURN_AS_TIMEZONE_AWARE
        and "default" == settings.RETURN_AS_TIMEZONE_AWARE
        and not ptz
    ):
        date_obj = date_obj.replace(tzinfo=None)

    return date_obj


class DateParser:
    def parse(
        self,
        date_string: str,
        parse_method: Callable[
            ...,
            tuple[datetime, str | None] | tuple[datetime, str | None, tuple[str, ...]],
        ],
        settings: Settings | dict[str, Any] | None = None,
        date_order: str | None = None,
    ) -> tuple[datetime, str | None]:
        date_obj, period, _ = self._parse_with_parts(
            date_string, parse_method, settings=settings, date_order=date_order
        )
        return date_obj, period

    @apply_settings
    def _parse_with_parts(
        self,
        date_string: str,
        parse_method: Callable[
            ...,
            tuple[datetime, str | None] | tuple[datetime, str | None, tuple[str, ...]],
        ],
        settings: Settings | dict[str, Any] | None = None,
        date_order: str | None = None,
    ) -> tuple[datetime, str | None, tuple[str, ...]]:
        assert isinstance(settings, Settings)
        date_string = str(date_string)

        if not date_string.strip():
            raise ValueError("Empty string")

        date_string = strip_braces(date_string)
        date_string, ptz = pop_tz_offset_from_string(date_string, settings=settings)

        result = parse_method(
            date_string, settings=settings, tz=ptz, date_order=date_order
        )
        date_obj, period = result[:2]
        parts = result[2] if len(result) == 3 else ()

        date_obj = _apply_timezone_settings(date_obj, ptz, settings)

        return date_obj, period, parts


date_parser = DateParser()
