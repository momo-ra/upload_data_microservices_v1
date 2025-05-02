from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

# ✅ Schema for `Tag`
class TagSchema(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., example="Temperature Sensor")
    description: Optional[str] = Field(None, example="Monitors room temperature")
    unit_of_measure: Optional[str] = Field(None, example="°C")

# ✅ Schema for `TimeSeries`
class TimeSeriesSchema(BaseModel):
    id: Optional[int] = None
    tag_id: int
    timestamp: datetime
    value: float = Field(..., example=25.5)

# ✅ Schema for `Alerts`
class AlertSchema(BaseModel):
    id: Optional[int] = None
    tag_id: int
    timestamp: datetime
    message: str = Field(..., example="Temperature exceeded threshold")