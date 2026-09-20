from pydantic import BaseModel


class TokenResponse(BaseModel):
    """
    Returned by POST /auth/refresh and POST /auth/2fa/verify.

    The refresh token is no longer included in the response body — it is
    delivered as an httpOnly cookie by the server.  Only the short-lived
    access token is returned here so the client can attach it to API calls
    via the Authorization header.
    """
    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """
    Returned by POST /auth/login.

    When 2FA is not enabled: access_token is populated and the refresh token
    is set as an httpOnly cookie by the server.

    When 2FA is enabled: access_token is empty, requires_2fa=True, and
    pre_auth_token holds a short-lived single-use token the client must send
    to POST /auth/2fa/verify together with the TOTP code.
    """
    access_token: str = ""
    token_type: str = "bearer"
    requires_2fa: bool = False
    pre_auth_token: str = ""


class LogoutRequest(BaseModel):
    # Kept for backward compatibility — the body refresh_token (if sent) is
    # also revoked.  The httpOnly cookie refresh token is always revoked.
    refresh_token: str | None = None


class CreateUserRequest(BaseModel):
    email: str
    password: str
    employee_id: int


# ── 2FA schemas ──────────────────────────────────────────────────────────────

class TwoFASetupResponse(BaseModel):
    """Returned by POST /auth/2fa/setup — client shows the QR URI to the user."""
    otp_auth_uri: str   # otpauth://totp/... — pass to a QR library
    secret: str         # raw base32 secret for manual entry


class TwoFAConfirmRequest(BaseModel):
    """Sent to POST /auth/2fa/confirm — confirms setup with the first code."""
    code: str           # 6-digit TOTP code from the authenticator app


class TwoFAVerifyRequest(BaseModel):
    """Sent to POST /auth/2fa/verify — completes login when 2FA is required."""
    pre_auth_token: str  # short-lived token from LoginResponse
    code: str            # 6-digit TOTP code


class TwoFADisableRequest(BaseModel):
    """Sent to POST /auth/2fa/disable — turns off 2FA after re-confirmation."""
    code: str           # current TOTP code to prove possession of the device
