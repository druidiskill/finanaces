from __future__ import annotations

from typing import Any

from app.interfaces.messenger.tg.constants import INCOME_DESTINATION_LABELS, INCOME_SOURCE_LABELS, INCOME_TAX_LABELS
from app.interfaces.messenger.tg.services import database


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

    wallet_lines = [f"- {wallet.name}: {wallet.summ:.2f}" for wallet in wallets]

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
    pending_tasks = database.transfer_tasks.list_pending()
    if not pending_tasks:
        return "🧾 Задачи\nНет активных задач по переводу."
    return f"🧾 Задачи по переводу\nАктивных задач: {len(pending_tasks)}\nВыберите задачу:"


def build_task_detail_text(task_id: int) -> str:
    wallet_map = database.get_wallet_map()
    task = database.get_transfer_task(task_id)
    if task is None:
        return "🧾 Задача не найдена."

    from_wallet = wallet_map.get(task.from_wallet_id)
    to_wallet = wallet_map.get(task.to_wallet_id)
    from_name = from_wallet.name if from_wallet else f"#{task.from_wallet_id}"
    to_name = to_wallet.name if to_wallet else f"#{task.to_wallet_id}"
    return (
        "🧾 Задача по переводу\n"
        f"ID: {task.id}\n"
        f"Откуда: {from_name}\n"
        f"Куда: {to_name}\n"
        f"Сумма: {task.amount:.2f}\n"
        f"Статус: {task.status}\n"
        f"Создана: {task.created_at}"
    )


def build_today_report_text() -> str:
    totals = database.get_day_totals()
    gross_income_total = round(database.income_transactions.total_for_date(totals["date"]), 2)
    legal_tax_lines = [f"{index}) {item['taxes_amount']:.2f}" for index, item in enumerate(totals["legal_taxes_items"], start=1)]
    legal_taxes_text = "\n".join(legal_tax_lines) if legal_tax_lines else "нет"

    return (
        f"📅 Отчет за {totals['date']}\n"
        f"💰 Доходы: {gross_income_total:.2f}\n"
        f"👨‍🏫 Учителям: {totals['teachers_total']:.2f}\n"
        f"🧾 Налоги от физ. лиц: {totals['physical_taxes_total']:.2f}\n"
        f"🏢 Налоги от юр. лиц:\n{legal_taxes_text}\n"
        f"💸 Расходы: {totals['expense_total']:.2f}"
    )


def build_wallets_report_text() -> str:
    wallets = database.wallets.list_all()
    lines = ["👛 Кошельки:"]
    if not wallets:
        lines.append("Нет кошельков.")
    else:
        total_amount = 0.0
        for index, wallet in enumerate(wallets, start=1):
            lines.append(f"{index}) {wallet.name}: {wallet.summ:.2f}")
            total_amount += wallet.summ
        lines.append("")
        lines.append(f"Итого: {total_amount:.2f}")
    return "\n".join(lines)


def build_fixes_report_text() -> str:
    fixes = database.list_expense_categories("fixes")
    if not fixes:
        return "📌 Фиксированные\nНет активных записей."

    lines = ["📌 Фиксированные:"]
    for index, item in enumerate(fixes, start=1):
        percent = 100.0 if item.summ_fix == 0 else max(0.0, (item.summ_now / item.summ_fix) * 100)
        due_date = database.get_next_fix_due_date(item.date_day).strftime("%d.%m")
        lines.append(
            f"{index}) {item.name}: {item.summ_now:.0f}/{item.summ_fix:.0f} | {percent:.0f}% | {due_date}"
        )
    return "\n".join(lines)


def build_needen_report_text() -> str:
    items = database.needen.list_active()
    if not items:
        return "🔁 Постоянные\nНет активных записей."

    lines = ["🔁 Постоянные:"]
    for index, item in enumerate(items, start=1):
        percent = 0.0 if item.summ_need == 0 else (item.summ_now / item.summ_need) * 100
        lines.append(f"{index}) {item.name}: {item.summ_now:.2f}/{item.summ_need:.2f} | {percent:.2f}%")
    return "\n".join(lines)


def build_reports_transfers_text() -> str:
    pending_tasks = database.transfer_tasks.list_pending()
    if not pending_tasks:
        return "🔄 Переводы\nНет активных задач."

    wallet_map = database.get_wallet_map()
    lines = ["🔄 Переводы:"]
    for index, task in enumerate(pending_tasks, start=1):
        from_wallet = wallet_map.get(task.from_wallet_id)
        to_wallet = wallet_map.get(task.to_wallet_id)
        from_name = from_wallet.name if from_wallet else f"#{task.from_wallet_id}"
        to_name = to_wallet.name if to_wallet else f"#{task.to_wallet_id}"
        lines.append(f"{index}) {from_name} -> {to_name}: {task.amount:.2f}")
    return "\n".join(lines)
