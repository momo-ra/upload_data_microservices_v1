from utils.log import setup_logger
from services.db_services import fetch_all

logger = setup_logger(__name__)

DEFAULT_LIMITS = {
    "5LTI077PV": {"min": 0, "max": 500},
    "5LFC022OP": {"min": 10, "max": 1000}
}

def validate_data(tag_id, timestamp, value):
    tag_name = f"Tag_{tag_id}"
    
    if tag_name in DEFAULT_LIMITS:
        min_val, max_val = DEFAULT_LIMITS[tag_name]["min"], DEFAULT_LIMITS[tag_name]["max"]
        if value < min_val or value > max_val:
            reason = f"Value {value} is outside the allowed range ({min_val} - {max_val})"
            logger.warning(f"⚠️ Abnormal value detected for tag {tag_id}: {reason}")
            return True, reason

    # **Check if the (tag_id, timestamp) already exists**
    check_query = "SELECT 1 FROM time_series WHERE tag_id = :tag_id AND timestamp = :timestamp LIMIT 1"
    existing = fetch_all(check_query, [{"tag_id": tag_id, "timestamp": timestamp}])
    
    if existing:
        reason = "Duplicate entry detected."
        logger.info(f"ℹ️ Duplicate entry for tag {tag_id} at {timestamp}: {reason}")
        return True, reason

    return False, None