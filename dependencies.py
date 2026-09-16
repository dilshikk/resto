"""
Заглушки зависимостей авторизации — для наглядности примеров роутеров.
В реальной реализации: проверка JWT (веб) / Telegram initData (бот),
подгрузка employee/user из БД, проверка permission_level по роли.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer()


async def get_current_employee(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Возвращает текущего сотрудника (любая роль) по JWT/Telegram-токену."""
    # TODO: декодировать токен, найти employee в БД
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="stub")


async def get_current_manager(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Возвращает текущего пользователя с ролью не ниже 'manager' (permission_level >= X)."""
    # TODO: декодировать токен, проверить roles.category == 'management'
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="stub")
