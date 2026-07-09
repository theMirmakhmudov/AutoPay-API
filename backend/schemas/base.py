from typing import TypeVar, Generic, Optional, Any
from pydantic import BaseModel, Field

T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    """
    Standardized API response wrapper used across the entire application.
    Ensures all API endpoints return a consistent structure.
    """
    success: bool = Field(..., description="Indicates if the API call was successful")
    message: str = Field(..., description="Human-readable message or error description")
    data: Optional[T] = Field(default=None, description="The actual payload/data of the response")
    error_code: Optional[str] = Field(default=None, description="Optional internal error code for debugging")

def create_success_response(data: T, message: str = "Success") -> BaseResponse[T]:
    return BaseResponse(success=True, message=message, data=data)

def create_error_response(message: str, error_code: Optional[str] = None) -> BaseResponse[Any]:
    return BaseResponse(success=False, message=message, error_code=error_code, data=None)
