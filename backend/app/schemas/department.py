from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DepartmentBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    location: str
    floor: str
    extension: Optional[str] = None
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentRead(DepartmentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
