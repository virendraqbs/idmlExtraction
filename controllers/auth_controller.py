"""
controllers/auth_controller.py — Authentication controller.

Routes:
    GET  /           → redirect to dashboard or login
    GET  /login      → login form
    POST /login      → authenticate and create session
    GET  /logout     → clear session

Authentication order:
  1. If LDAP_ENABLED=true → try LDAP bind; on success, accept.
  2. Fall back to ADMIN_USER / ADMIN_PASS from .env.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates

from config import config

logger = logging.getLogger(__name__)

auth_router = APIRouter()
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


def _ldap_authenticate(username: str, password: str) -> bool:
    """Return True if the user's credentials are accepted by the LDAP server."""
    if not password:
        return False
    try:
        from ldap3 import ALL, SUBTREE, Connection, Server
        from ldap3.core.exceptions import LDAPException

        server = Server(
            config.LDAP_HOST,
            port=config.LDAP_PORT,
            use_ssl=config.LDAP_USE_SSL,
            get_info=ALL,
        )

        # Step 1: bind with the service account to find the user's full DN
        conn = Connection(server, user=config.LDAP_BIND_DN, password=config.LDAP_BIND_PASS)
        if not conn.bind():
            logger.error("LDAP service-account bind failed: %s", conn.result)
            return False

        search_filter = config.LDAP_USER_FILTER.format(username=username)
        conn.search(
            search_base=config.LDAP_BASE_DN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=["distinguishedName"],
        )

        if not conn.entries:
            logger.warning("LDAP: no user found for '%s'", username)
            return False

        user_dn = conn.entries[0].entry_dn
        conn.unbind()

        # Step 2: bind as the found user to verify the password
        user_conn = Connection(server, user=user_dn, password=password)
        result = user_conn.bind()
        user_conn.unbind()
        return result

    except LDAPException as exc:
        logger.error("LDAP authentication error: %s", exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected LDAP error: %s", exc)
        return False


@auth_router.get("/")
async def index(request: Request):
    if request.session.get("logged_in"):
        return RedirectResponse(url="/dashboard", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@auth_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@auth_router.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(""), password: str = Form("")):
    authenticated = False

    if config.LDAP_ENABLED:
        authenticated = _ldap_authenticate(username, password)

    # Fall back to local admin credentials
    if not authenticated:
        authenticated = (username == config.ADMIN_USER and password == config.ADMIN_PASS)

    if authenticated:
        request.session["logged_in"] = True
        request.session["username"] = username
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid credentials. Please try again."},
    )


@auth_router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
