
def format_seconds(time: int) -> str:
    """Convert the given amount of seconds into a hh:mm:ss format"""
    time = int(time)

    hours = time // 3600
    time %= 3600
    minutes = time // 60
    seconds = time % 60

    if hours > 0:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"
