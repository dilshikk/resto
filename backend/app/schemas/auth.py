from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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
