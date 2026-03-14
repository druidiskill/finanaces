from __future__ import annotations

from typing import Any

from bot_app.constants import INCOME_DESTINATION_LABELS, INCOME_SOURCE_LABELS, INCOME_TAX_LABELS
from bot_app.services import database


def format_distribution_preview(data: dict[str, Any], distribution: dict[str, float]) -> str:
    path = [INCOME_TAX_LABELS[data["tax_mode"]]]
    if data["source_type"] != "none":
        path.append(INCOME_SOURCE_LABELS[data["source_type"]])
    if not (data["tax_mode"] == "taxable" and data["source_type"] == "legal"):
        path.append(INCOME_DESTINATION_LABELS[data["destination"]])

    return (
        "Подтвердите запись дохода:\n"
        f"Путь: {' -> '.join(path)}\n"
        f"Сумма: {distribution['amount']:.2f}\n"
        f"Учителям: {distribution['teachers_amount']:.2f}\n"
        f"Налоги: {distribution['taxes_amount']:.2f}\n"
        f"Личные: {distribution['personal_amount']:.2f}"
    )


def build_financial_overview_text() -> str:
    snapshot = database.get_financial_snapshot()
    totals = snapshot["totals"]
    wallets = snapshot["wallets"]
    pending_tasks = snapshot["pending_tasks"]
    nearest_fix = snapshot["nearest_fix"]

    wallet_lines = []
    for wallet in wallets:
        wallet_lines.append(f"- {wallet.name}: {wallet.summ:.2f}")

    nearest_fix_line = "нет"
    if nearest_fix is not None:
        nearest_fix_line = (
            f"{nearest_fix.name} | {nearest_fix.summ_now:.2f}/{nearest_fix.summ_fix:.2f} | до {nearest_fix.date_day} числа"
        )

    return (
        f"📅 Сегодня: {totals['date']}\n"
        f"💰 Доходы: {totals['income_total']:.2f}\n"
        f"👨‍🏫 Учителям: {totals['teachers_total']:.2f}\n"
        f"🧾 Налоги от физ. лиц: {totals['physical_taxes_total']:.2f}\n"
        f"🏢 Налоги от юр. лиц: {len(totals['legal_taxes_items'])} шт.\n"
        f"💸 Расходы: {totals['expense_total']:.2f}\n"
        f"🧾 Задачи: {len(pending_tasks)}\n"
        f"🎯 Ближайшая цель: {nearest_fix_line}\n\n"
        "👛 Кошельки:\n"
        + ("\n".join(wallet_lines) if wallet_lines else "- нет")
    )


def build_tasks_text() -> str:
    wallet_map = database.get_wallet_map()
    pending_tasks = database.transfer_tasks.list_pending()
    if not pending_tasks:
        return "🧾 Задачи\nНет активных задач по переводу."

    lines = ["🧾 Задачи по переводу:"]
    for index, task in enumerate(pending_tasks, start=1):
        from_wallet = wallet_map.get(task.from_wallet_id)
        to_wallet = wallet_map.get(task.to_wallet_id)
        from_name = from_wallet.name if from_wallet else f"#{task.from_wallet_id}"
        to_name = to_wallet.name if to_wallet else f"#{task.to_wallet_id}"
        lines.append(f"{index}) {from_name} -> {to_name}: {task.amount:.2f}")
    return "\n".join(lines)
