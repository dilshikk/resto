import pyotp

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

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
    RefreshRequest,
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


def _verify_totp(secret: str, code: str) -> bool:
    """Return True if `code` is a valid current TOTP code for `secret`."""
    totp = pyotp.TOTP(secret)
    # valid_window=1 accepts the previous and next 30-second window to tolerate
    # small clock skew between the server and the user's device.
    return totp.verify(code, valid_window=1)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,  # required by SlowAPI for IP extraction
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Password-based login with two-layer brute-force protection:

    Layer 1 — per-IP rate limit (SlowAPI): max 10 requests/minute from a
    single IP address.  Returns HTTP 429 on excess.

    Layer 2 — per-email lockout (LoginAttemptTracker): after 5 consecutive
    wrong passwords the account is locked for 15 minutes regardless of the
    source IP.  This stops distributed attacks that rotate IPs to bypass the
    per-IP limit.  A correct password resets the failure counter.
    """
    email = form_data.username.lower().strip()

    # ── Layer 2: check per-email lockout ─────────────────────────────────────
    if login_attempt_tracker.is_locked(email):
        secs = login_attempt_tracker.seconds_remaining(email)
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
        # Always record the failure (including unknown email) so an attacker
        # can't distinguish "email not found" from "wrong password" via lockout
        # timing.  Unknown emails are tracked under the address they submitted.
        login_attempt_tracker.record_failure(email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )

    # Correct password — clear the failure counter for this email.
    login_attempt_tracker.record_success(email)

    # ── 2FA gate ──────────────────────────────────────────────────────────────
    # If 2FA is enabled the client must complete a second step before receiving
    # real tokens.  We issue a short-lived pre-auth token instead so there is
    # nothing useful an attacker can do with stolen credentials alone.
    if user.is_2fa_enabled and user.totp_secret:
        pre_auth_token = create_pre_auth_token(user.id)
        return LoginResponse(requires_2fa=True, pre_auth_token=pre_auth_token)

    # No 2FA — issue tokens immediately.
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return LoginResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/2fa/verify", response_model=TokenResponse)
@limiter.limit("20/minute")
async def verify_2fa(
    request: Request,  # required by SlowAPI for IP extraction
    body: TwoFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a pre-auth token + valid TOTP code for a full access/refresh pair.

    Called after POST /auth/login returns requires_2fa=True.

    Rate-limited to 20 requests/minute per IP to prevent TOTP brute-forcing
    (the 6-digit code space is only 1 000 000 values).
    """
    payload = decode_pre_auth_token(body.pre_auth_token)
    user = (await db.execute(select(User).where(User.id == int(payload["sub"])))).scalar_one_or_none()
    if not user or not user.is_2fa_enabled or not user.totp_secret:
        raise HTTPException(status_code=401, detail="Недействительный pre-auth токен")

    if not _verify_totp(user.totp_secret, body.code.strip()):
        raise HTTPException(status_code=400, detail="Неверный код аутентификатора")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


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
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token, "refresh")
    if payload.get("jti") and await is_token_revoked(payload["jti"], db):
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Rotate: the old refresh token must not be usable again once a new pair
    # has been issued from it.
    await revoke_token(payload, db)

    access_token = create_access_token({"sub": str(user.id)})
    new_refresh = create_refresh_token({"sub": str(user.id)})
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


@router.post("/logout")
async def logout(
    body: LogoutRequest | None = None,
    token: str = Depends(oauth2_scheme),
    # Use get_current_web_user (not get_current_user) so that users who have
    # not yet linked an employee profile can still log out.  get_current_user
    # resolves an EmployeeAccount and raises 403 when none exists, which would
    # leave the access token alive with no way for the user to revoke it.
    current_user: User = Depends(get_current_web_user),
    db: AsyncSession = Depends(get_db),
):
    """
    End the session: revoke the access token used to call this endpoint (so
    it cannot be replayed for the rest of its lifetime) and, if the client
    sends its refresh token, revoke that too (so it cannot be used to mint
    fresh access tokens after logout).

    Accessible to every authenticated web user, including those who have not
    yet completed the onboarding flow and have no linked employee profile.
    """
    access_payload = decode_token(token, "access")
    await revoke_token(access_payload, db)

    if body and body.refresh_token:
        try:
            refresh_payload = decode_token(body.refresh_token, "refresh")
            await revoke_token(refresh_payload, db)
        except HTTPException:
            # An already-invalid/expired refresh token needs no revocation.
            pass

    await db.commit()
    return {"ok": True}


@router.post("/create-user", include_in_schema=False)
async def create_user_internal(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
):
    """Создаёт веб-пользователя и привязывает его к сотруднику. Только при пустой БД.

    Принимает данные в теле запроса (JSON), а не в query-параметрах, чтобы
    пароль не попадал в URL (логи сервера, история браузера, referrer).
    """
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
