import logging
from datetime import datetime
from decimal import Decimal

import gspread_asyncio
from google.oauth2.service_account import Credentials

from .config import (
    GOOGLE_SHEET_ID,
    GOOGLE_WORKSHEET_NAME,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOALS_WORKSHEET_NAME,
    SCOPES,
)
from .utils import normalize_kind, parse_sheet_amount, parse_sheet_date, split_category_path


def get_creds():
    return Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )


agcm = gspread_asyncio.AsyncioGspreadClientManager(get_creds)


async def get_main_ws():
    client = await agcm.authorize()
    sheet = await client.open_by_key(GOOGLE_SHEET_ID)
    return await sheet.worksheet(GOOGLE_WORKSHEET_NAME)


async def get_goals_ws():
    client = await agcm.authorize()
    sheet = await client.open_by_key(GOOGLE_SHEET_ID)
    return await sheet.worksheet(GOALS_WORKSHEET_NAME)


async def load_categories_from_sheet(kind: str) -> list[str]:
    try:
        worksheet = await get_main_ws()
        kind_values = await worksheet.col_values(2)
        category_values = await worksheet.col_values(4)
    except Exception:
        logging.exception("Failed to load categories from sheet")
        return []
    categories = []
    seen = set()
    target_kind = normalize_kind(kind)
    for row_kind, row_category in zip(kind_values, category_values):
        if row_category is None:
            continue
        item = str(row_category).strip()
        if not item:
            continue
        kind_item = str(row_kind).strip()
        if kind_item == "kind" or kind_item == "тип":
            continue
        if target_kind and kind_item != target_kind:
            continue
        lower = item.lower()
        if lower in {"category", "category_path", "категория", "категория_path"}:
            continue
        if item in seen:
            continue
        seen.add(item)
        categories.append(item)
    return categories


async def append_row(row: list[str]):
    worksheet = await get_main_ws()
    await worksheet.append_row(
        row,
        value_input_option="USER_ENTERED",
        table_range="A1",
    )


async def load_rows_from_sheet() -> list[list[str]]:
    try:
        worksheet = await get_main_ws()
        return await worksheet.get_all_values()
    except Exception:
        logging.exception("Failed to load rows from sheet")
        return []


def summarize_rows(rows: list[list[str]], kind: str, start_date, end_date, prefix: list[str]):
    total = Decimal("0.00")
    buckets: dict[str, Decimal] = {}
    target_kind = normalize_kind(kind)

    for row in rows:
        if len(row) < 4:
            continue
        date_value = parse_sheet_date(row[0])
        if not date_value:
            header = str(row[0]).strip().lower()
            if header in {"date", "дата", "timestamp"}:
                continue
            continue
        row_kind = str(row[1]).strip()
        if target_kind and row_kind != target_kind:
            continue
        if date_value < start_date or date_value > end_date:
            continue
        amount = parse_sheet_amount(row[2])
        if amount is None:
            continue
        category = str(row[3]).strip()
        parts = split_category_path(category)
        if prefix:
            if parts[: len(prefix)] != prefix:
                continue
            group_key = parts[len(prefix)] if len(parts) > len(prefix) else ""
        else:
            group_key = parts[0] if parts else ""
        total += amount
        if group_key:
            buckets[group_key] = buckets.get(group_key, Decimal("0.00")) + amount

    return total, buckets


def compute_net_profit(rows: list[list[str]]):
    income = Decimal("0.00")
    expense = Decimal("0.00")
    for row in rows:
        if len(row) < 3:
            continue
        row_kind = str(row[1]).strip()
        if row_kind in {"kind", "тип"}:
            continue
        amount = parse_sheet_amount(row[2])
        if amount is None:
            continue
        if row_kind == "Доход":
            income += amount
        elif row_kind == "Расход":
            expense += amount
    return income - expense


async def append_goal_row(row: list[str]):
    worksheet = await get_goals_ws()
    await worksheet.append_row(
        row,
        value_input_option="USER_ENTERED",
        table_range="A1",
    )


async def load_goals_rows() -> list[list[str]]:
    try:
        worksheet = await get_goals_ws()
        return await worksheet.get_all_values()
    except Exception:
        logging.exception("Failed to load goals rows")
        return []


def index_goals(rows: list[list[str]]):
    index: dict[str, tuple[int, list[str]]] = {}
    for i, row in enumerate(rows):
        if not row:
            continue
        header = str(row[0]).strip().lower()
        if header in {"id"}:
            continue
        goal_id = str(row[0]).strip()
        if not goal_id:
            continue
        index[goal_id] = (i + 1, row)
    return index


def build_goal_row(
    goal_id: str,
    parent_id: str,
    path: str,
    item_type: str,
    title: str,
    status: str,
    due_date: str,
    created_at: str,
    updated_at: str,
    order: str,
    note: str,
    owner: str,
):
    return [
        goal_id,
        parent_id,
        path,
        item_type,
        title,
        status,
        due_date,
        created_at,
        updated_at,
        order,
        note,
        owner,
    ]


def build_goal_tree(rows: list[list[str]]):
    nodes: dict[str, dict] = {}
    children: dict[str, list[str]] = {}
    for row in rows:
        if len(row) < 6:
            continue
        header = str(row[0]).strip().lower()
        if header in {"id"}:
            continue
        goal_id = str(row[0]).strip()
        if not goal_id:
            continue
        parent_id = str(row[1]).strip() if len(row) > 1 else ""
        path = str(row[2]).strip() if len(row) > 2 else ""
        item_type = str(row[3]).strip() if len(row) > 3 else ""
        title = str(row[4]).strip() if len(row) > 4 else ""
        status = str(row[5]).strip() if len(row) > 5 else ""
        due_date = str(row[6]).strip() if len(row) > 6 else ""
        note = str(row[10]).strip() if len(row) > 10 else ""
        nodes[goal_id] = {
            "id": goal_id,
            "parent_id": parent_id,
            "path": path,
            "type": item_type,
            "title": title,
            "status": status,
            "due_date": due_date,
            "note": note,
        }
        children.setdefault(parent_id, []).append(goal_id)
    return nodes, children


def is_goal_done(goal_id: str, nodes: dict, children: dict, memo: dict) -> bool:
    if goal_id in memo:
        return memo[goal_id]
    kids = children.get(goal_id, [])
    if not kids:
        memo[goal_id] = nodes.get(goal_id, {}).get("status") == "done"
        return memo[goal_id]
    memo[goal_id] = all(is_goal_done(kid, nodes, children, memo) for kid in kids)
    return memo[goal_id]


def effective_goal_status(goal_id: str, nodes: dict, children: dict) -> str:
    memo: dict[str, bool] = {}
    if is_goal_done(goal_id, nodes, children, memo):
        return "done"
    return nodes.get(goal_id, {}).get("status", "todo")


def build_goal_items(nodes: dict, children: dict, parent_id: str, status_emoji):
    ids = children.get(parent_id, [])
    memo: dict[str, bool] = {}
    items = []
    for goal_id in ids:
        node = nodes.get(goal_id)
        if not node:
            continue
        kids = children.get(goal_id, [])
        done_section = bool(kids) and is_goal_done(goal_id, nodes, children, memo)
        due = parse_sheet_date(node.get("due_date"))
        due_key = due if due else datetime.max.date()
        label = node.get("title") or node.get("path") or goal_id
        status = effective_goal_status(goal_id, nodes, children)
        label = f"{status_emoji(status)} {label}"
        items.append(
            {
                "id": goal_id,
                "label": label,
                "due_key": due_key,
                "done_section": done_section,
            }
        )
    items.sort(key=lambda item: (item["done_section"], item["due_key"], item["label"].lower()))
    return items
