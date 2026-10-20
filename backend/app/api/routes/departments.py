from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.department import Department
from app.schemas.department import DepartmentRead

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=List[DepartmentRead], summary="List hospital departments")
def list_departments(
    active_only: bool = Query(True, description="Filter only active departments"),
    search: Optional[str] = Query(None, description="Search by name, code, or wing location"),
    db: Session = Depends(get_db),
) -> List[Department]:
    """Retrieve hospital departments with optional filtering."""
    query = db.query(Department)
    if active_only:
        query = query.filter(Department.is_active == True)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            Department.name.ilike(s) | Department.code.ilike(s) | Department.location.ilike(s)
        )
    return query.order_by(Department.name).all()


@router.get("/{department_id}", response_model=DepartmentRead, summary="Get department details")
def get_department(department_id: int, db: Session = Depends(get_db)) -> Department:
    """Retrieve details for a specific hospital department."""
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {department_id} not found",
        )
    return dept
