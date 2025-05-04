"""Common type definitions used throughout the application."""
import datetime
from enum import Enum
import google.generativeai.types as types

class SearchMethod(Enum):
    NONE = 0
    CUSTOM = 1
    GEMINI_GROUNDING = 2
    # Add other values as needed from your original implementation


def get_real_time_data():
    """Return the current date and time as a string."""
    now = datetime.datetime.now()
    return f"The current date and time is: {now.strftime('%Y-%m-%d %H:%M:%S')}."

def get_formatted_datetime_info():
    """Return a formatted string with day abbreviation and date/time."""
    current_time = datetime.datetime.now()
    day_abbr = current_time.strftime("%a")[:3]
    formatted_datetime = current_time.strftime("%Y-%m-%d %H:%M:%S")
    return f"{day_abbr} {formatted_datetime}"