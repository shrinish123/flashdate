from flashdate.calendars import CalendarBase
from flashdate.calendars.hijri_parser import hijri_parser


class HijriCalendar(CalendarBase):
    parser = hijri_parser
