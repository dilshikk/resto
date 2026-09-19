from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """
    Returned by POST /auth/login.

    When 2FA is not enabled the response looks like a normal TokenResponse
    (access_token + refresh_token are set, requires_2fa is False).

    When 2FA is enabled access_token and refresh_token are empty strings and
    pre_auth_token holds a short-lived single-use token the client must send
    to POST /auth/2fa/verify together with the TOTP code.  Full tokens are
    issued only after the TOTP code is accepted.
    """
    access_token: str = ""
    refresh_token: str = ""
    token_type: str = "bearer"
    requires_2fa: bool = False
    pre_auth_token: str = ""


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    # Optional so old frontend builds that call POST /auth/logout with no body
    # still work (the access token from the Authorization header is always
    # revoked either way) — but a refresh token here also gets revoked, which
    # is required to actually end the session rather than just discard it
    # client-side.
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
