"""Auth endpoints. Thin: parse the request, call auth_service, shape the response."""
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import login_rate_limit
from app.core.security import REFRESH_TOKEN_DAYS
from app.database.session import get_db
from app.models import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, MeResponse, TokenResponse
from app.schemas.user import UserRead
from app.services import auth_service
from app.services.auth_service import TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "amcos_refresh"
COOKIE_PATH = "/api/v1/auth"  # the browser only sends the cookie to auth endpoints


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE, token, max_age=REFRESH_TOKEN_DAYS * 86400, path=COOKIE_PATH,
        httponly=True,                                         # JavaScript can't read it (XSS)
        secure=get_settings().environment == "production",     # HTTPS-only in production
        samesite="strict",                                     # not sent by other sites (CSRF)
    )


def _token_response(response: Response, tokens: TokenPair) -> TokenResponse:
    _set_refresh_cookie(response, tokens.refresh_token)
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_rate_limit)])
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    tokens = auth_service.login(db, body.email, body.password,
                                ip=request.client.host if request.client else None,
                                user_agent=request.headers.get("user-agent"))
    return _token_response(response, tokens)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    tokens = auth_service.refresh(db, request.cookies.get(REFRESH_COOKIE), request.headers.get("user-agent"))
    return _token_response(response, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    auth_service.logout(db, request.cookies.get(REFRESH_COOKIE))
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    base = UserRead.model_validate(user).model_dump()
    return MeResponse(**base, permissions=sorted(user.permission_codes))


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: ChangePasswordRequest, response: Response,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    auth_service.change_password(db, user, body.current_password, body.new_password)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
