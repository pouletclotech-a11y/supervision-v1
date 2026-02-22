from datetime import date, timedelta
from typing import Set

class CalendarService:
    @staticmethod
    def get_french_holidays(year: int) -> Set[date]:
        """
        Returns a set of French public holidays for a given year.
        Includes fixed dates and calculated dates (Easter-based).
        """
        holidays = set()
        
        # Fixed dates
        holidays.add(date(year, 1, 1))   # Jour de l'an
        holidays.add(date(year, 5, 1))   # Fête du travail
        holidays.add(date(year, 5, 8))   # Victoire 1945
        holidays.add(date(year, 7, 14))  # Fête nationale
        holidays.add(date(year, 8, 15))  # Assomption
        holidays.add(date(year, 11, 1))  # Toussaint
        holidays.add(date(year, 11, 11)) # Armistice
        holidays.add(date(year, 12, 25)) # Noël
        
        # Easter (Meeus/Jones/Butcher algorithm)
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        easter = date(year, month, day)
        
        # Variable dates based on Easter
        holidays.add(easter + timedelta(days=1))   # Lundi de Pâques
        holidays.add(easter + timedelta(days=39))  # Ascension
        holidays.add(easter + timedelta(days=50))  # Lundi de Pentecôte
        
        return holidays

    @staticmethod
    def is_holiday(d: date) -> bool:
        holidays = CalendarService.get_french_holidays(d.year)
        return d in holidays

    @staticmethod
    def is_weekend(d: date) -> bool:
        # 5 = Saturday, 6 = Sunday
        return d.weekday() >= 5
        
    @staticmethod
    def is_working_hours(d: date, start_hour=8, end_hour=18) -> bool:
        """
        Simple working hours check (Mon-Fri, not holiday, between hours).
        """
        if CalendarService.is_weekend(d):
            return False
        if CalendarService.is_holiday(d):
            return False
        if start_hour <= d.hour < end_hour: # strict strictly less than end_hour? convention usually yes.
            return True
        return False
