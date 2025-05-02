import pandas as pd

async def determine_frequency(df: pd.DataFrame, timestamp_column: str) -> str:
    """Determine the frequency of the data based on the timestamp column."""
    # Ensure the timestamp column exists
    if timestamp_column not in df.columns:
        raise ValueError(f"❌ Column '{timestamp_column}' not found! Available columns: {df.columns.tolist()}")

    # Convert the column to datetime if not already
    df[timestamp_column] = pd.to_datetime(df[timestamp_column], errors='coerce')

    # Remove empty values
    df = df.dropna(subset=[timestamp_column])

    # Calculate the time difference in seconds
    df = df.sort_values(timestamp_column)
    df["time_diff"] = df[timestamp_column].diff().dt.total_seconds()
    median_diff = df["time_diff"].median()

    if pd.isna(median_diff):
        return None
    elif median_diff < 1:
        return "sub_second"
    elif median_diff < 60:
        return "second"
    elif median_diff < 3600:
        return "minute"
    elif median_diff < 86400:
        return "hour"
    elif median_diff < 604800:
        return "day"
    else:
        return "week"
async def get_hypertable_name(frequency:str) -> str:
    """
    Get the name of the hypertable based on the frequency of the data.
    """
    mapping = {
        "sub_second": "time_bucket_second",
        "second": "time_bucket_minute",
        "minute": "time_bucket_hour",
        "hour": "time_bucket_day",
        "day": "time_bucket_week",
        "week": "time_bucket_month",
        "month": "time_bucket_year",
    }
    return mapping.get(frequency, "time_bucket_day")