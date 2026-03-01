"""
controllers/auth_controller.py — Authentication controller.

Routes:
    GET  /           → redirect to dashboard or login
    GET  /login      → login form
    POST /login      → authenticate and create session
    GET  /logout     → clear session
"""
from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates

from config import config

auth_router = APIRouter()
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


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
    if username == config.ADMIN_USER and password == config.ADMIN_PASS:
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
