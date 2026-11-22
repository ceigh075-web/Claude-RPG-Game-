"""In-game calendar. All time is stored as integer total minutes since the epoch (1 Thawmoon 412)."""

MIN_PER_HOUR = 60
HOURS_PER_DAY = 24
DAYS_PER_WEEK = 7
WEEKS_PER_MONTH = 4
DAYS_PER_MONTH = DAYS_PER_WEEK * WEEKS_PER_MONTH  # 28
MONTHS_PER_YEAR = 12
DAYS_PER_YEAR = DAYS_PER_MONTH * MONTHS_PER_YEAR  # 336
MIN_PER_DAY = MIN_PER_HOUR * HOURS_PER_DAY
START_YEAR = 412

MONTHS = ["Thawmoon", "Seedmoon", "Bloomtide", "Highsun", "Embertide", "Harvestmoon",
          "Leaffall", "Mistmoon", "Frostfall", "Deepwinter", "Ironfrost", "Lastlight"]
WEEKDAYS = ["Moonday", "Tiwday", "Wendday", "Thornday", "Freyday", "Starday", "Sunday"]
SEASONS = ["spring", "spring", "spring", "summer", "summer", "summer",
           "autumn", "autumn", "autumn", "winter", "winter", "winter"]


class GameClock:
    def __init__(self, minutes=8 * MIN_PER_HOUR):
        self.minutes = float(minutes)  # float so sub-minute real-time ticks accumulate

    # ---- advancing
    def advance(self, minutes):
        self.minutes += minutes

    def advance_hours(self, hours):
        self.minutes += hours * MIN_PER_HOUR

    # ---- derived values
    @property
    def total_minutes(self):
        return int(self.minutes)

    @property
    def day_index(self):
        """Days since epoch (0-based)."""
        return self.total_minutes // MIN_PER_DAY

    @property
    def hour(self):
        return (self.total_minutes // MIN_PER_HOUR) % HOURS_PER_DAY

    @property
    def minute(self):
        return self.total_minutes % MIN_PER_HOUR

    @property
    def hour_float(self):
        return (self.minutes / MIN_PER_HOUR) % HOURS_PER_DAY

    @property
    def year(self):
        return START_YEAR + self.day_index // DAYS_PER_YEAR

    @property
    def month_index(self):
        return (self.day_index % DAYS_PER_YEAR) // DAYS_PER_MONTH

    @property
    def month_name(self):
        return MONTHS[self.month_index]

    @property
    def day_of_month(self):
        return self.day_index % DAYS_PER_MONTH + 1

    @property
    def week_of_month(self):
        return (self.day_of_month - 1) // DAYS_PER_WEEK + 1

    @property
    def week_index(self):
        return self.day_index // DAYS_PER_WEEK

    @property
    def weekday(self):
        return WEEKDAYS[self.day_index % DAYS_PER_WEEK]

    @property
    def season(self):
        return SEASONS[self.month_index]

    @property
    def is_night(self):
        return self.hour >= 21 or self.hour < 5

    def daylight(self):
        """0.0 (midnight) .. 1.0 (day) used for lighting."""
        h = self.hour_float
        if 7 <= h < 18:
            return 1.0
        if 5 <= h < 7:
            return 0.35 + 0.65 * (h - 5) / 2
        if 18 <= h < 21:
            return 1.0 - 0.65 * (h - 18) / 3
        return 0.35

    def time_str(self):
        return f"{self.hour:02d}:{self.minute:02d}"

    def date_str(self):
        return f"{self.weekday}, {self.day_of_month} {self.month_name} {self.year}"

    def stamp(self):
        """Compact (day, minute-of-day) for memory records."""
        return self.day_index, self.total_minutes % MIN_PER_DAY

    def to_dict(self):
        return {"minutes": self.minutes}

    @classmethod
    def from_dict(cls, d):
        return cls(d["minutes"])


def format_stamp(day_index, minute_of_day=0):
    year = START_YEAR + day_index // DAYS_PER_YEAR
    month = MONTHS[(day_index % DAYS_PER_YEAR) // DAYS_PER_MONTH]
    dom = day_index % DAYS_PER_MONTH + 1
    return f"{dom} {month} {year}, {minute_of_day // 60:02d}:{minute_of_day % 60:02d}"
