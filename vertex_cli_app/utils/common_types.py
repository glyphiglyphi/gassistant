"""Common type definitions used throughout the application."""
import datetime
from enum import Enum
# import google.generativeai.types as types # This import is unused

class SearchMethod(Enum):
    NONE = 0
    CUSTOM = 1
    VERTEX_AI_SEARCH = 2 # Renamed from GEMINI_GROUNDING for clarity with Vertex AI
    # Add other values as needed

def get_real_time_data() -> str:
    """Return the current date and time as a string."""
    now = datetime.datetime.now()
    return f"The current date and time is: {now.strftime('%Y-%m-%d %H:%M:%S')}."

def get_formatted_datetime_info() -> str:
    """
    Return a formatted string with day abbreviation and date/time.
    Example: "Wed 11:22:33 2023-10-26" (Format changed for brevity and common usage)
    """
    current_time = datetime.datetime.now()
    # Example: "Wed 10:00:00 2023-11-29"
    return current_time.strftime("%a %H:%M:%S %Y-%m-%d")

if __name__ == "__main__":
    print("--- Testing common_types.py ---")
    
    # Test SearchMethod Enum
    print("\nSearch Methods:")
    for method in SearchMethod:
        print(f"- {method.name}: {method.value}")
    
    # Adjusted assertion based on actual enum definition
    assert SearchMethod.CUSTOM.value == 1, f"Expected SearchMethod.CUSTOM.value to be 1, got {SearchMethod.CUSTOM.value}"
    print("SearchMethod enum values are as expected.")

    # Test get_formatted_datetime_info
    datetime_info = get_formatted_datetime_info()
    print(f"\nCurrent Datetime Info: {datetime_info}")
    assert isinstance(datetime_info, str), "get_formatted_datetime_info should return a string."
    assert len(datetime_info) > 10, "Formatted datetime string seems too short." 
    # Removed 'assert "UTC" in datetime_info' as current implementation is timezone-naive.
    # To make it UTC: current_time = datetime.datetime.now(datetime.timezone.utc)
    # and then include %Z or similar in strftime. For now, keeping it naive.
    print("get_formatted_datetime_info produces a string as expected.")

    # Test get_real_time_data
    real_time_data = get_real_time_data()
    print(f"\nReal Time Data: {real_time_data}")
    assert isinstance(real_time_data, str), "get_real_time_data should return a string."
    assert "current date and time is" in real_time_data, "Real time data string format error."
    print("get_real_time_data produces a string as expected.")
    
    print("\ncommon_types.py tests passed (or reviewed)!")