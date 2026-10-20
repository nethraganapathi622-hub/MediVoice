"""Staff Authentication API.

HARDENING NOTES:
----------------
1. Credential Discovery:
   Public staff enumeration (/api/auth/staff-accounts) has been REMOVED to prevent user discovery.
2. Production Boundary:
   Synthetic staff credentials are only recognized when ENVIRONMENT == 'development'.
   In production/staging, authenticate_staff returns None, requiring integration with the hospital's
   authoritative LDAP / Active Directory / OAuth2 IdP.
3. Cryptographic Token Integrity:
   Tokens are HMAC-SHA256 signed using settings.SECRET_KEY. Client-supplied roles or unverified IDs
   are never trusted without cryptographic signature verification.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import (
    StaffUser,
    TokenResponse,
    authenticate_staff,
    create_staff_access_token,
    get_current_staff,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class StaffLoginRequest(BaseModel):
    staff_id: str = Field(..., description="Staff identification number (e.g., EMP-4091)")
    passcode: str = Field(..., description="Staff access passcode")


@router.post("/staff-token", response_model=TokenResponse, summary="Obtain a signed staff JWT access token")
def login_staff(payload: StaffLoginRequest) -> TokenResponse:
    """Authenticate staff and issue a cryptographically signed HMAC-SHA256 JWT.

    Synthetic accounts are available in development mode only.
    """
    staff = authenticate_staff(payload.staff_id, payload.passcode)
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid staff credentials. Verify employee ID and passcode.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_staff_access_token(staff)
    expires_at = datetime.now(timezone.utc)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        staff=staff,
        expires_at=expires_at,
    )


@router.get("/me", response_model=StaffUser, summary="Verify current staff token")
def get_current_user_profile(staff: StaffUser = Depends(get_current_staff)) -> StaffUser:
    """Return validated claims from the verified Bearer access token."""
    return staff
