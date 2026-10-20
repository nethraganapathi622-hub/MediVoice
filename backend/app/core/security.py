from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()
security_bearer = HTTPBearer(auto_error=False)

# Pre-configured synthetic staff accounts for hospital operations
SYNTHETIC_STAFF: Dict[str, Dict[str, str]] = {
    "EMP-4091": {
        "name": "Nurse Supervisor Jackson",
        "role": "TriageLead",
        "passcode": "hospital123",
        "department": "Emergency",
    },
    "EMP-1022": {
        "name": "Dr. Robert Chen",
        "role": "Doctor",
        "passcode": "hospital123",
        "department": "Cardiology",
    },
    "EMP-2041": {
        "name": "Dr. Elena Rostova",
        "role": "Doctor",
        "passcode": "hospital123",
        "department": "Neurology",
    },
    "EMP-8801": {
        "name": "Admin Sarah Collins",
        "role": "Admin",
        "passcode": "hospital123",
        "department": "Administration",
    },
    "EMP-3310": {
        "name": "Nurse Radha Nair",
        "role": "ChargeNurse",
        "passcode": "hospital123",
        "department": "Triage",
    },
}


class StaffUser(BaseModel):
    staff_id: str
    name: str
    role: str
    department: Optional[str] = None


class PatientUser(BaseModel):
    phone: str
    patient_id: Optional[int] = None
    name: Optional[str] = None
    role: str = "patient"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    staff: StaffUser
    expires_at: datetime


class PatientTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    patient: PatientUser
    expires_at: datetime



def authenticate_staff(staff_id: str, passcode: str) -> Optional[StaffUser]:
    """Verify synthetic staff credentials.

    HARDENING CONSTRAINT:
    Synthetic development accounts are strictly disabled outside of explicit development mode.
    """
    if not settings.is_development:
        return None

    account = SYNTHETIC_STAFF.get(staff_id)
    if not account:
        return None
    if account["passcode"] != passcode:
        return None
    return StaffUser(
        staff_id=staff_id,
        name=account["name"],
        role=account["role"],
        department=account.get("department"),
    )


def create_staff_access_token(staff: StaffUser, expires_delta: Optional[timedelta] = None) -> str:
    """Issue a cryptographically signed HMAC-SHA256 JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": staff.staff_id,
        "name": staff.name,
        "role": staff.role,
        "dept": staff.department,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": "medivoice-auth",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_staff_access_token(token: str) -> StaffUser:
    """Decode and validate a signed JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer="medivoice-auth",
        )
        staff_id: str = payload.get("sub")
        role: str = payload.get("role")
        name: str = payload.get("name")
        department: Optional[str] = payload.get("dept")

        if not staff_id or not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims: missing subject or role",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return StaffUser(staff_id=staff_id, name=name, role=role, department=department)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(err)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_staff(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> StaffUser:
    """FastAPI dependency: Extract and verify bearer token for protected endpoints."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing or empty Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_staff_access_token(auth.credentials)


def require_staff_roles(allowed_roles: List[str]):
    """Role-based authorization dependency factory."""

    def role_checker(staff: StaffUser = Depends(get_current_staff)) -> StaffUser:
        if staff.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Staff role '{staff.role}' is not authorized. Required: {', '.join(allowed_roles)}",
            )
        return staff

    return role_checker


def create_patient_access_token(
    phone: str,
    patient_id: Optional[int] = None,
    name: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Issue a cryptographically signed HMAC-SHA256 JWT access token for patient self-service."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=7))
    payload = {
        "sub": phone,
        "patient_id": patient_id,
        "name": name or "Verified Patient",
        "role": "patient",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": "medivoice-auth",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_patient_access_token(token: str) -> PatientUser:
    """Decode and validate a signed patient JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer="medivoice-auth",
        )
        phone: str = payload.get("sub")
        patient_id: Optional[int] = payload.get("patient_id")
        name: Optional[str] = payload.get("name")
        role: str = payload.get("role", "patient")

        if not phone:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid patient token: missing phone subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return PatientUser(phone=phone, patient_id=patient_id, name=name, role=role)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Patient session has expired. Please verify your phone number again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid patient token: {str(err)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_patient(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> PatientUser:
    """FastAPI dependency: Extract and verify patient bearer token."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Patient authentication required: Missing or empty Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_patient_access_token(auth.credentials)

