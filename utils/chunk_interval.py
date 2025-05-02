async def get_chunk_interval(frequency):
    return {
        'sub_second': '1 hour',
        'second': '1 day',
        'minute': '7 days',
        'hour': '30 days',
        'day': '180 days',
        'week': '365 days'
    }.get(frequency, '30 days')