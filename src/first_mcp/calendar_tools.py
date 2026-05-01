"""
Calendar and date utility tools for First MCP Server.
"""

import calendar
from datetime import datetime
from typing import Dict, Any


def get_calendar(year: int, month: int) -> Dict[str, Any]:
    """
    Get a calendar for a specified year and month.

    Args:
        year: The year (e.g., 2025)
        month: The month (1-12)

    Returns:
        Dictionary with calendar in HTML format, plain text, and metadata
    """
    try:
        if not (1 <= month <= 12):
            return {"error": "Month must be between 1 and 12"}

        if year < 1:
            return {"error": "Year must be positive"}

        html_cal = calendar.HTMLCalendar(firstweekday=0)
        calendar_html = html_cal.formatmonth(year, month)
        cal_text = calendar.month(year, month)
        month_name = calendar.month_name[month]
        month_abbr = calendar.month_abbr[month]
        days_in_month = calendar.monthrange(year, month)[1]
        first_weekday = calendar.monthrange(year, month)[0]
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        first_weekday_name = weekday_names[first_weekday]
        is_leap_year = calendar.isleap(year)

        today = datetime.now()
        is_current_month = (today.year == year and today.month == month)
        current_day = today.day if is_current_month else None

        return {
            "success": True,
            "year": year,
            "month": month,
            "month_name": month_name,
            "month_abbreviation": month_abbr,
            "calendar_html": calendar_html,
            "calendar_text": cal_text,
            "days_in_month": days_in_month,
            "first_day_of_month": first_weekday_name,
            "is_leap_year": is_leap_year,
            "is_current_month": is_current_month,
            "current_day": current_day,
            "format_note": "calendar_html provides structured data for easy parsing; calendar_text is human-readable fallback"
        }

    except Exception as e:
        return {"error": str(e)}


def get_day_of_week(date_string: str) -> Dict[str, Any]:
    """
    Get the day of the week for a given date in ISO format (YYYY-MM-DD).

    Args:
        date_string: Date in ISO format (e.g., "2025-08-09")

    Returns:
        Dictionary with weekday information and metadata
    """
    try:
        try:
            date_obj = datetime.strptime(date_string, "%Y-%m-%d")
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD format (e.g., '2025-08-09')"}

        weekday_number = date_obj.weekday()
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekday_name = weekday_names[weekday_number]
        weekday_abbr = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][weekday_number]
        is_weekend = weekday_number >= 5

        today = datetime.now().date()
        date_as_date = date_obj.date()

        return {
            "success": True,
            "date": date_string,
            "weekday_name": weekday_name,
            "weekday_abbreviation": weekday_abbr,
            "weekday_number": weekday_number,
            "is_weekend": is_weekend,
            "is_weekday": not is_weekend,
            "is_today": date_as_date == today,
            "is_past": date_as_date < today,
            "is_future": date_as_date > today,
            "year": date_obj.year,
            "month": date_obj.month,
            "day": date_obj.day
        }

    except Exception as e:
        return {"error": str(e)}
