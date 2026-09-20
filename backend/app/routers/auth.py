import pyotp

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.auth import (
    verify_password,
    create_access_token,
    create_refresh_token,
    create_pre_auth_token,
    decode_pre_auth_token,
    hash_password,
    get_current_user,
    get_current_web_user,
    decode_token,
    is_token_revoked,
    revoke_token,
    oauth2_scheme,
)
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.employee import Employee, EmployeeAccount
from app.models.role import Role
from app.rate_limit import limiter, login_attempt_tracker
from app.schemas.auth import (
    TokenResponse,
    LoginResponse,
    LogoutRequest,
    CreateUserRequest,
    TwoFASetupResponse,
    TwoFAConfirmRequest,
    TwoFAVerifyRequest,
    TwoFADisableRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Issuer label shown in authenticator apps (e.g. Google Authenticator).
_APP_NAME = "MADO Checklist"

# Cookie name for the httpOnly refresh token.
_REFRESH_COOKIE = "refresh_token"

# The cookie is scoped to auth endpoints only — the browser will not send it
# on any other API call, minimising its exposure.
_REFRESH_COOKIE_PATH = "/api/v1/auth"

# Stable integer key for the advisory lock that guards first-user creation.
_FIRST_USER_LOCK_KEY = 0x4D41_444F  # "MADO" in hex


def _set_refresh_cookie(response: Response, token: str) -> None:
    """
    Deliver the refresh token as an httpOnly cookie.

    httpOnly  — JavaScript cannot read or steal the token via XSS.
    Secure    — sent only over HTTPS (configurable for local HTTP dev).
    SameSite  — "none" for cross-origin frontends; falls back to "lax" when
                Secure is disabled (browsers reject None without Secure).
    Path      — scoped to /api/v1/auth so it is never attached to data API
                calls, reducing the token's attack surface.
    """
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.effective_samesite,  # type: ignore[arg-type]
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
        path=_REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh-token cookie on logout."""
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path=_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.effective_samesite,  # type: ignore[arg-type]
    )


def _verify_totp(secret: str, code: str) -> bool:
    """Return True if `code` is a valid current TOTP code for `secret`."""
    totp = pyotp.TOTP(secret)
    # valid_window=1 accepts the previous and next 30-second window to tolerate
    # small clock skew between the server and the user's device.
    return totp.verify(code, valid_window=1)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Password-based login with two-layer brute-force protection:

    Layer 1 — per-IP rate limit (SlowAPI): max 10 requests/minute from a
    single IP address.  Returns HTTP 429 on excess.

    Layer 2 — per-email lockout (DbLoginAttemptTracker): after 5 consecutive
    wrong passwords the account is locked for 15 minutes regardless of the
    source IP.  Counters are stored in PostgreSQL so they survive restarts
    and are shared across all replicas.  A correct password resets the counter.

    On success the refresh token is delivered as an httpOnly cookie — it is
    never exposed in the JSON response body.
    """
    email = form_data.username.lower().strip()

    # ── Layer 2: check per-email lockout ─────────────────────────────────────
    if await login_attempt_tracker.is_locked(email):
        secs = await login_attempt_tracker.seconds_remaining(email)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Слишком много неудачных попыток входа. "
                f"Повторите через {secs // 60} мин. {secs % 60} сек."
            ),
        )

    # ── Credential check ─────────────────────────────────────────────────────
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        await login_attempt_tracker.record_failure(email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )

    await login_attempt_tracker.record_success(email)

    # ── 2FA gate ──────────────────────────────────────────────────────────────
    if user.is_2fa_enabled and user.totp_secret:
        pre_auth_token = create_pre_auth_token(user.id)
        return LoginResponse(requires_2fa=True, pre_auth_token=pre_auth_token)

    # ── Issue tokens ──────────────────────────────────────────────────────────
    # Refresh token → httpOnly cookie (invisible to JS).
    # Access token  → JSON response body (held in memory by the client).
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    _set_refresh_cookie(response, refresh_token)
    return LoginResponse(access_token=access_token)


@router.post("/2fa/verify", response_model=TokenResponse)
@limiter.limit("20/minute")
async def verify_2fa(
    request: Request,
    response: Response,
    body: TwoFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a pre-auth token + valid TOTP code for a full access/refresh pair.

    Called after POST /auth/login returns requires_2fa=True.
    The refresh token is delivered as an httpOnly cookie, not in the body.
    """
    payload = decode_pre_auth_token(body.pre_auth_token)
    user = (await db.execute(select(User).where(User.id == int(payload["sub"])))).scalar_one_or_none()
    if not user or not user.is_2fa_enabled or not user.totp_secret:
        raise HTTPException(status_code=401, detail="Недействительный pre-auth токен")

    if not _verify_totp(user.totp_secret, body.code.strip()):
        raise HTTPException(status_code=400, detail="Неверный код аутентификатора")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a new TOTP secret for the authenticated user and return the
    otpauth:// URI for QR display.  The secret is stored but 2FA is NOT yet
    enabled — the user must confirm with POST /auth/2fa/confirm first.
    """
    if current_user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA уже включена")

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.email, issuer_name=_APP_NAME)

    current_user.totp_secret = secret
    await db.commit()

    return TwoFASetupResponse(otp_auth_uri=uri, secret=secret)


@router.post("/2fa/confirm")
async def confirm_2fa(
    body: TwoFAConfirmRequest,
    current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the first code from the authenticator app to prove the user has
    successfully scanned the QR and enable 2FA on the account.
    """
    if current_user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA уже включена")
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Сначала вызовите POST /auth/2fa/setup")

    if not _verify_totp(current_user.totp_secret, body.code.strip()):
        raise HTTPException(status_code=400, detail="Неверный код. Убедитесь, что время устройства верно")

    current_user.is_2fa_enabled = True
    await db.commit()
    return {"ok": True, "message": "2FA успешно включена"}


@router.post("/2fa/disable")
async def disable_2fa(
    body: TwoFADisableRequest,
    current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Disable 2FA after confirming possession of the authenticator device.
    Requires the current TOTP code so an attacker who steals an active session
    cannot silently turn off 2FA without the physical device.
    """
    if not current_user.is_2fa_enabled or not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA не включена")

    if not _verify_totp(current_user.totp_secret, body.code.strip()):
        raise HTTPException(status_code=400, detail="Неверный код аутентификатора")

    current_user.is_2fa_enabled = False
    current_user.totp_secret = None
    await db.commit()
    return {"ok": True, "message": "2FA отключена"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Silently rotate the refresh token and issue a new access token.

    The refresh token is read from the httpOnly cookie — no request body is
    needed.  A new refresh token is issued and the old one is revoked
    (token rotation), so a stolen cookie can only be used once before the
    legitimate client's next refresh invalidates it.
    """
    stored_refresh = request.cookies.get(_REFRESH_COOKIE)
    if not stored_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token отсутствует",
        )

    payload = decode_token(stored_refresh, "refresh")
    if payload.get("jti") and await is_token_revoked(payload["jti"], db):
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Refresh token отозван")

    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    # Rotate: revoke the old refresh token before issuing a new pair.
    await revoke_token(payload, db)

    access_token = create_access_token({"sub": str(user.id)})
    new_refresh = create_refresh_token({"sub": str(user.id)})
    await db.commit()

    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    body: LogoutRequest | None = None,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_db),
):
    """
    End the session: revoke the access token and the refresh token (from the
    httpOnly cookie), then clear the cookie.
    """
    access_payload = decode_token(token, "access")
    await revoke_token(access_payload, db)

    cookie_refresh = request.cookies.get(_REFRESH_COOKIE)
    if cookie_refresh:
        try:
            refresh_payload = decode_token(cookie_refresh, "refresh")
            await revoke_token(refresh_payload, db)
        except HTTPException:
            pass

    if body and body.refresh_token:
        try:
            body_payload = decode_token(body.refresh_token, "refresh")
            await revoke_token(body_payload, db)
        except HTTPException:
            pass

    await db.commit()
    _clear_refresh_cookie(response)
    return {"ok": True}


@router.post("/create-user", include_in_schema=False)
async def create_user_internal(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
):
    """Создаёт веб-пользователя и привязывает его к сотруднику. Только при пустой БД.

    Защищено от гонки через транзакционный advisory lock PostgreSQL:
    второй одновременный запрос увидит count=1 и получит 403.
    """
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)").bindparams(key=_FIRST_USER_LOCK_KEY))

    count_result = await db.execute(select(func.count()).select_from(User))
    count = count_result.scalar_one()
    if count > 0:
        raise HTTPException(status_code=403, detail="Users already exist")

    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()

    account = EmployeeAccount(employee_id=body.employee_id, user_id=user.id)
    db.add(account)
    await db.commit()
    return {"user_id": user.id}
