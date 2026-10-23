"""HTTP boundary: exact origins, cookies and strict metadata inputs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.identity_security import AuthError, DeactivateInput, LoginInput, RegisterInput, ThemeInput

router = APIRouter(prefix="/api", tags=["identity"])


class PublicUser(BaseModel):
    id: UUID
    email: str
    role: Literal["admin", "member"]
    active: bool
    theme: Literal["light", "dark"]


class SessionCreated(BaseModel):
    user: PublicUser


class SessionView(SessionCreated):
    csrf_cookie: str
    expires_at: datetime


class InvitationCreated(BaseModel):
    id: UUID
    token: str
    expires_at: datetime


class InvitationView(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    redeemed_at: datetime | None
    revoked_at: datetime | None


def context(request: Request, mutation=False):
    settings = request.app.state.settings
    if mutation and request.headers.get("origin") not in settings.allowed_origins:
        raise AuthError(403, "origin_failed", "This request origin is not allowed")
    return (
        request.app.state.identity,
        request.cookies.get(settings.session_cookie),
        request.headers.get("x-csrf-token"),
    )


def clear_cookies(response: Response, settings):
    for name, hidden in ((settings.session_cookie, True), (settings.csrf_cookie, False)):
        response.delete_cookie(
            name,
            path="/",
            secure=not settings.insecure_loopback_cookies,
            httponly=hidden,
            samesite="strict",
        )


def signed_in(request, response, result):
    payload, session, csrf = result
    settings = request.app.state.settings
    for name, value, hidden in (
        (settings.session_cookie, session, True),
        (settings.csrf_cookie, csrf, False),
    ):
        response.set_cookie(
            name,
            value,
            max_age=7 * 86400,
            path="/",
            httponly=hidden,
            secure=not settings.insecure_loopback_cookies,
            samesite="strict",
        )
    return payload


@router.post("/auth/login", response_model=SessionCreated)
def login(data: LoginInput, request: Request, response: Response):
    identity, old, _ = context(request, True)
    return signed_in(
        request,
        response,
        identity.login(
            data,
            old,
            request.client.host if request.client else "unknown",
            request.state.request_id,
        ),
    )


@router.post("/auth/invitations/redeem", status_code=201, response_model=SessionCreated)
def redeem(data: RegisterInput, request: Request, response: Response):
    identity, old, _ = context(request, True)
    return signed_in(
        request,
        response,
        identity.redeem(
            data,
            old,
            request.client.host if request.client else "unknown",
            request.state.request_id,
        ),
    )


@router.get("/auth/me", response_model=SessionView)
def me(request: Request):
    identity, session, _ = context(request)
    return identity.me(session)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    identity, session, csrf = context(request, True)
    identity.logout(session, csrf, request.state.request_id)
    clear_cookies(response, request.app.state.settings)


@router.get("/admin/invitations", response_model=list[InvitationView])
def invitations(request: Request):
    identity, session, _ = context(request)
    return identity.invitations(session)


@router.post("/admin/invitations", status_code=201, response_model=InvitationCreated)
def create_invitation(request: Request):
    identity, session, csrf = context(request, True)
    return identity.create_invitation(session, csrf, request.state.request_id)


@router.post("/admin/invitations/{identifier}/revoke", status_code=204)
def revoke_invitation(identifier: UUID, request: Request):
    identity, session, csrf = context(request, True)
    identity.revoke_invitation(session, csrf, identifier, request.state.request_id)


@router.get("/admin/users", response_model=list[PublicUser])
def users(request: Request):
    identity, session, _ = context(request)
    return identity.users(session)


@router.patch("/admin/users/{identifier}", status_code=204)
def deactivate(identifier: UUID, data: DeactivateInput, request: Request):
    identity, session, csrf = context(request, True)
    identity.change_user(session, csrf, identifier, request.state.request_id, deactivate=True)


@router.post("/admin/users/{identifier}/revoke-sessions", status_code=204)
def revoke_sessions(identifier: UUID, request: Request):
    identity, session, csrf = context(request, True)
    identity.change_user(session, csrf, identifier, request.state.request_id, deactivate=False)


@router.patch("/users/me/preferences", status_code=204)
def theme(data: ThemeInput, request: Request):
    identity, session, csrf = context(request, True)
    identity.theme(session, csrf, data.theme)
