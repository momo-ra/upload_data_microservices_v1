from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Generic, TypeVar


T = TypeVar('T')

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



class PaginationModel(BaseModel):
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of items per page")
    total: int = Field(..., description="Total number of items")
    hasMore: bool = Field(..., description="Whether there are more pages")


class ResponseModel(BaseModel, Generic[T]):
    status: str = Field(..., description="Response status, e.g., 'success' or 'fail'")
    data: Optional[T] = Field(None, description="Response data, can be any type")
    message: Optional[str] = Field(None, description="Optional message providing additional context")
    pagination: Optional[PaginationModel] = Field(None, description="Pagination information")
    # errors: Optional[List[str]] = Field(None, description="List of error messages if any")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "data": {"key": "value"},
                "message": "Operation completed successfully",
                "errors": None
            }
        }
