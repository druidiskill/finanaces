from aiogram import Router

from app.interfaces.messenger.tg.handlers import admin, expenses, income, reports, start, tasks


def setup_routers() -> Router:
    root_router = Router()
    root_router.include_router(start.router)
    root_router.include_router(income.router)
    root_router.include_router(expenses.router)
    root_router.include_router(reports.router)
    root_router.include_router(tasks.router)
    root_router.include_router(admin.router)
    return root_router
