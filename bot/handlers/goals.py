import logging
import uuid
from datetime import datetime

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..helpers import delete_user_message, edit_or_answer
from ..keyboards import (
    build_cancel_kb,
    build_goal_status_kb,
    build_goals_children_kb,
    build_goals_leaf_kb,
    build_goals_root_kb,
)
from ..sheets import (
    append_goal_row,
    build_goal_items,
    build_goal_tree,
    effective_goal_status,
    get_goals_ws,
    index_goals,
    load_goals_rows,
)
from ..states import GoalsFlow
from ..utils import (
    format_status_ru,
    get_user_name,
    is_allowed,
    parse_sheet_date,
    status_emoji,
)


async def show_goals_root_from_callback(callback: CallbackQuery, state: FSMContext):
    rows = await load_goals_rows()
    nodes, children = build_goal_tree(rows)
    items = build_goal_items(nodes, children, "", status_emoji)
    text = "🎯 Цели:" if items else "🎯 Цели пока не добавлены."
    await state.update_data(current_goal_id="", current_parent_id="")
    await edit_or_answer(callback, text, reply_markup=build_goals_root_kb(items))


async def show_goals_root_from_message(message: Message, state: FSMContext):
    rows = await load_goals_rows()
    nodes, children = build_goal_tree(rows)
    items = build_goal_items(nodes, children, "", status_emoji)
    text = "🎯 Цели:" if items else "🎯 Цели пока не добавлены."
    await state.update_data(current_goal_id="", current_parent_id="")
    await message.answer(text, reply_markup=build_goals_root_kb(items))


async def show_goals_node_from_callback(callback: CallbackQuery, state: FSMContext, goal_id: str):
    rows = await load_goals_rows()
    nodes, children = build_goal_tree(rows)
    node = nodes.get(goal_id)
    if not node:
        await show_goals_root_from_callback(callback, state)
        return
    parent_id = node.get("parent_id", "")
    await state.update_data(current_goal_id=goal_id, current_parent_id=parent_id)
    items = build_goal_items(nodes, children, goal_id, status_emoji)
    title = node.get("title") or node.get("path") or goal_id
    status = effective_goal_status(goal_id, nodes, children)
    status_ru = format_status_ru(status)
    due = node.get("due_date") or "не задан"
    note = node.get("note") or ""
    note_block = f"\nКомментарии:\n{note}" if note else ""
    if items:
        text = f"🎯 {title}\nСтатус: {status_ru}\nСрок: {due}{note_block}\nВыберите этап:"
        await edit_or_answer(
            callback,
            text,
            reply_markup=build_goals_children_kb(items, parent_id, show_add_step=True),
        )
        return
    text = f"🎯 {title}\nСтатус: {status_ru}\nСрок: {due}{note_block}"
    await edit_or_answer(
        callback,
        text,
        reply_markup=build_goals_leaf_kb(parent_id, status),
    )


async def show_goals_node_from_message(message: Message, state: FSMContext, goal_id: str):
    rows = await load_goals_rows()
    nodes, children = build_goal_tree(rows)
    node = nodes.get(goal_id)
    if not node:
        await show_goals_root_from_message(message, state)
        return
    parent_id = node.get("parent_id", "")
    await state.update_data(current_goal_id=goal_id, current_parent_id=parent_id)
    items = build_goal_items(nodes, children, goal_id, status_emoji)
    title = node.get("title") or node.get("path") or goal_id
    status = effective_goal_status(goal_id, nodes, children)
    status_ru = format_status_ru(status)
    due = node.get("due_date") or "не задан"
    note = node.get("note") or ""
    note_block = f"\nКомментарии:\n{note}" if note else ""
    if items:
        text = f"🎯 {title}\nСтатус: {status_ru}\nСрок: {due}{note_block}\nВыберите этап:"
        await message.answer(
            text,
            reply_markup=build_goals_children_kb(items, parent_id, show_add_step=True),
        )
        return
    text = f"🎯 {title}\nСтатус: {status_ru}\nСрок: {due}{note_block}"
    await message.answer(
        text,
        reply_markup=build_goals_leaf_kb(parent_id, status),
    )


async def on_section_goals(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await state.clear()
    await show_goals_root_from_callback(callback, state)
    await callback.answer()


async def on_goals_open(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    goal_id = (callback.data or "").split(":", 1)[1]
    await show_goals_node_from_callback(callback, state, goal_id)
    await callback.answer()


async def on_goals_back(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    parent_id = (callback.data or "").split(":", 1)[1]
    if parent_id:
        await show_goals_node_from_callback(callback, state, parent_id)
    else:
        await show_goals_root_from_callback(callback, state)
    await callback.answer()


async def on_goals_add_goal(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await state.set_state(GoalsFlow.waiting_goal_title)
    await edit_or_answer(callback, "➕🎯 Введите название цели:", reply_markup=build_cancel_kb())
    await callback.answer()


async def on_goals_add_goal_title(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    title = message.text.strip()
    if not title:
        await message.answer("⚠️ Название цели не должно быть пустым.")
        await delete_user_message(message)
        return
    await state.update_data(goal_title=title)
    await state.set_state(GoalsFlow.waiting_goal_due)
    await message.answer("📅 Введите срок (ДД.ММ.ГГГГ):", reply_markup=build_cancel_kb())
    await delete_user_message(message)


async def on_goals_add_goal_due(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    due = message.text.strip()
    if not parse_sheet_date(due):
        await message.answer("⚠️ Неверный формат даты. Пример: 21.01.2026")
        await delete_user_message(message)
        return
    data = await state.get_data()
    title = data.get("goal_title", "").strip()
    if not title:
        await message.answer("⚠️ Название цели не найдено.")
        await delete_user_message(message)
        return
    goal_id = f"G{uuid.uuid4().hex[:8]}"
    today = datetime.now().strftime("%d.%m.%Y")
    row = [
        goal_id,
        "",
        title,
        "goal",
        title,
        "todo",
        due,
        today,
        today,
        "0",
        "",
        get_user_name(message.from_user.id),
    ]
    try:
        await append_goal_row(row)
    except Exception:
        logging.exception("Failed to append goal row")
        await message.answer("❗ Ошибка записи цели. Проверьте доступы.")
        await delete_user_message(message)
        return
    await state.clear()
    await show_goals_root_from_message(message, state)
    await delete_user_message(message)


async def on_goals_add_step_current(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    parent_id = data.get("current_goal_id")
    if not parent_id:
        await callback.answer("⚠️ Сначала выберите цель.", show_alert=True)
        return
    rows = await load_goals_rows()
    nodes, _ = build_goal_tree(rows)
    parent_path = nodes.get(parent_id, {}).get("path", "")
    await state.update_data(parent_id=parent_id, parent_path=parent_path)
    await state.set_state(GoalsFlow.waiting_step_title)
    await edit_or_answer(callback, "➕🧩 Введите название этапа:", reply_markup=build_cancel_kb())
    await callback.answer()


async def on_goals_add_step_title(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    title = message.text.strip()
    if not title:
        await message.answer("⚠️ Название этапа не должно быть пустым.")
        await delete_user_message(message)
        return
    await state.update_data(step_title=title)
    await state.set_state(GoalsFlow.waiting_step_due)
    await message.answer("📅 Введите срок (ДД.ММ.ГГГГ):", reply_markup=build_cancel_kb())
    await delete_user_message(message)


async def on_goals_add_step_due(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    due = message.text.strip()
    if not parse_sheet_date(due):
        await message.answer("⚠️ Неверный формат даты. Пример: 21.01.2026")
        await delete_user_message(message)
        return
    data = await state.get_data()
    title = data.get("step_title", "").strip()
    parent_id = data.get("parent_id", "")
    parent_path = data.get("parent_path", "")
    if not title or not parent_id:
        await message.answer("⚠️ Не удалось определить родителя этапа.")
        await delete_user_message(message)
        return
    full_path = f"{parent_path} > {title}" if parent_path else title
    step_id = f"S{uuid.uuid4().hex[:8]}"
    today = datetime.now().strftime("%d.%m.%Y")
    row = [
        step_id,
        parent_id,
        full_path,
        "step",
        title,
        "todo",
        due,
        today,
        today,
        "0",
        "",
        get_user_name(message.from_user.id),
    ]
    try:
        await append_goal_row(row)
    except Exception:
        logging.exception("Failed to append step row")
        await message.answer("❗ Ошибка записи этапа. Проверьте доступы.")
        await delete_user_message(message)
        return
    await state.clear()
    await show_goals_node_from_message(message, state, parent_id)
    await delete_user_message(message)


async def on_goals_status_current(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    goal_id = data.get("current_goal_id")
    if not goal_id:
        await callback.answer("⚠️ Сначала выберите цель.", show_alert=True)
        return
    rows = await load_goals_rows()
    index = index_goals(rows)
    if goal_id not in index:
        await callback.answer("⚠️ ID не найден.", show_alert=True)
        return
    row_idx, _ = index[goal_id]
    await state.update_data(goal_row_idx=row_idx)
    await edit_or_answer(callback, "✅📌 Выберите статус:", reply_markup=build_goal_status_kb())
    await callback.answer()


async def on_goals_status_set(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    row_idx = data.get("goal_row_idx")
    current_id = data.get("current_goal_id")
    if not row_idx:
        await callback.answer("⚠️ Не выбран элемент.", show_alert=True)
        return
    status = (callback.data or "").split(":", 1)[1]
    today = datetime.now().strftime("%d.%m.%Y")
    try:
        worksheet = await get_goals_ws()
        await worksheet.update_cell(row_idx, 6, status)
        await worksheet.update_cell(row_idx, 9, today)
    except Exception:
        logging.exception("Failed to update goal status")
        await edit_or_answer(callback, "❗ Ошибка обновления статуса.")
        await callback.answer()
        return
    await state.clear()
    if current_id:
        await show_goals_node_from_callback(callback, state, current_id)
    else:
        await show_goals_root_from_callback(callback, state)
    await callback.answer()


async def on_goals_delegate_current(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    goal_id = data.get("current_goal_id")
    if not goal_id:
        await callback.answer("⚠️ Сначала выберите цель.", show_alert=True)
        return
    rows = await load_goals_rows()
    index = index_goals(rows)
    if goal_id not in index:
        await callback.answer("⚠️ ID не найден.", show_alert=True)
        return
    row_idx, _ = index[goal_id]
    await state.update_data(goal_row_idx=row_idx)
    await state.set_state(GoalsFlow.waiting_delegate_name)
    await edit_or_answer(callback, "👤 Введите имя исполнителя:", reply_markup=build_cancel_kb())
    await callback.answer()


async def on_goals_delegate_name(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    name = message.text.strip()
    if not name:
        await message.answer("⚠️ Имя не должно быть пустым.")
        await delete_user_message(message)
        return
    data = await state.get_data()
    row_idx = data.get("goal_row_idx")
    current_id = data.get("current_goal_id")
    today = datetime.now().strftime("%d.%m.%Y")
    try:
        worksheet = await get_goals_ws()
        await worksheet.update_cell(row_idx, 12, name)
        await worksheet.update_cell(row_idx, 9, today)
    except Exception:
        logging.exception("Failed to update goal owner")
        await message.answer("❗ Ошибка делегирования.")
        await delete_user_message(message)
        return
    await state.clear()
    if current_id:
        await show_goals_node_from_message(message, state, current_id)
    else:
        await show_goals_root_from_message(message, state)
    await delete_user_message(message)


async def on_goals_comment_current(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    goal_id = data.get("current_goal_id")
    if not goal_id:
        await callback.answer("⚠️ Сначала выберите цель.", show_alert=True)
        return
    rows = await load_goals_rows()
    index = index_goals(rows)
    if goal_id not in index:
        await callback.answer("⚠️ ID не найден.", show_alert=True)
        return
    row_idx, row = index[goal_id]
    note = str(row[10]).strip() if len(row) > 10 else ""
    await state.update_data(goal_row_idx=row_idx, existing_note=note)
    await state.set_state(GoalsFlow.waiting_comment_text)
    await edit_or_answer(callback, "💬 Введите комментарий:", reply_markup=build_cancel_kb())
    await callback.answer()


async def on_goals_comment_text(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.")
        await delete_user_message(message)
        return
    comment = message.text.strip()
    if not comment:
        await message.answer("⚠️ Комментарий не должен быть пустым.")
        await delete_user_message(message)
        return
    data = await state.get_data()
    row_idx = data.get("goal_row_idx")
    current_id = data.get("current_goal_id")
    existing = data.get("existing_note", "")
    stamp = datetime.now().strftime("%d.%m.%Y")
    new_note = (
        f"{existing}\n[{stamp}] {comment}".strip()
        if existing
        else f"[{stamp}] {comment}"
    )
    today = datetime.now().strftime("%d.%m.%Y")
    try:
        worksheet = await get_goals_ws()
        await worksheet.update_cell(row_idx, 11, new_note)
        await worksheet.update_cell(row_idx, 9, today)
    except Exception:
        logging.exception("Failed to update goal note")
        await message.answer("❗ Ошибка добавления комментария.")
        await delete_user_message(message)
        return
    await state.clear()
    if current_id:
        await show_goals_node_from_message(message, state, current_id)
    else:
        await show_goals_root_from_message(message, state)
    await delete_user_message(message)


async def on_goals_due_edit_current(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("??? ???????????? ????????????????.", show_alert=True)
        return
    data = await state.get_data()
    goal_id = data.get("current_goal_id")
    if not goal_id:
        await callback.answer("?????? ?????????????? ???????????????? ????????.", show_alert=True)
        return
    rows = await load_goals_rows()
    index = index_goals(rows)
    if goal_id not in index:
        await callback.answer("?????? ID ???? ????????????.", show_alert=True)
        return
    row_idx, row = index[goal_id]
    current_due = str(row[6]).strip() if len(row) > 6 else ""
    await state.update_data(goal_row_idx=row_idx, current_goal_id=goal_id)
    await state.set_state(GoalsFlow.waiting_due_edit)
    hint = f"??????? ????: {current_due}" if current_due else "???? ?? ?????."
    await edit_or_answer(
        callback,
        f"??? ??????? ????? ???? (??.??.????).
{hint}",
        reply_markup=build_cancel_kb(),
    )
    await callback.answer()


async def on_goals_due_edit_text(message: Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        await message.answer("??? ???????????? ????????????????.")
        await delete_user_message(message)
        return
    due = message.text.strip()
    if not parse_sheet_date(due):
        await message.answer("?????? ???????????????? ???????????? ????????. ????????????: 21.01.2026")
        await delete_user_message(message)
        return
    data = await state.get_data()
    row_idx = data.get("goal_row_idx")
    current_id = data.get("current_goal_id")
    if not row_idx:
        await message.answer("?????? ???? ???????????? ??????????????.")
        await delete_user_message(message)
        return
    today = datetime.now().strftime("%d.%m.%Y")
    try:
        worksheet = await get_goals_ws()
        await worksheet.update_cell(row_idx, 7, due)
        await worksheet.update_cell(row_idx, 9, today)
    except Exception:
        logging.exception("Failed to update due date")
        await message.answer("??? ???????????? ???????????????????? ????????.")
        await delete_user_message(message)
        return
    await state.clear()
    if current_id:
        await show_goals_node_from_message(message, state, current_id)
    else:
        await show_goals_root_from_message(message, state)
    await delete_user_message(message)


async def on_goals_schedule_current(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    await edit_or_answer(callback, "🗓️ Перенос в расписание — в разработке.")
    await callback.answer()


async def on_goals_delete_current(callback: CallbackQuery, state: FSMContext):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен.", show_alert=True)
        return
    data = await state.get_data()
    goal_id = data.get("current_goal_id")
    if not goal_id:
        await callback.answer("⚠️ Сначала выберите цель.", show_alert=True)
        return
    rows = await load_goals_rows()
    nodes, children = build_goal_tree(rows)
    ids_to_delete = []
    stack = [goal_id]
    while stack:
        current = stack.pop()
        ids_to_delete.append(current)
        stack.extend(children.get(current, []))
    if not ids_to_delete:
        await callback.answer("⚠️ Нечего удалять.", show_alert=True)
        return
    id_set = set(ids_to_delete)
    remaining_rows = []
    for row in rows:
        if not row:
            remaining_rows.append(row)
            continue
        header = str(row[0]).strip().lower()
        if header in {"id"}:
            remaining_rows.append(row)
            continue
        row_id = str(row[0]).strip()
        if row_id and row_id in id_set:
            continue
        remaining_rows.append(row)
    try:
        worksheet = await get_goals_ws()
        await worksheet.clear()
        if remaining_rows:
            await worksheet.update("A1", remaining_rows, value_input_option="USER_ENTERED")
    except Exception:
        logging.exception("Failed to delete goal rows")
        await edit_or_answer(callback, "❗ Ошибка удаления. Проверьте доступы.")
        await callback.answer()
        return
    parent_id = nodes.get(goal_id, {}).get("parent_id", "")
    if parent_id:
        await show_goals_node_from_callback(callback, state, parent_id)
    else:
        await show_goals_root_from_callback(callback, state)
    await callback.answer()


def register_goals(dp):
    dp.callback_query.register(on_section_goals, F.data == "section_goals")
    dp.callback_query.register(on_goals_open, F.data.startswith("goals_open:"))
    dp.callback_query.register(on_goals_back, F.data.startswith("goals_back:"))
    dp.callback_query.register(on_goals_add_goal, F.data == "goals_add_goal")
    dp.callback_query.register(on_goals_add_step_current, F.data == "goals_add_step_current")
    dp.callback_query.register(on_goals_status_current, F.data == "goals_status_current")
    dp.callback_query.register(on_goals_status_set, F.data.startswith("goals_status_set:"))
    dp.callback_query.register(on_goals_delegate_current, F.data == "goals_delegate_current")
    dp.callback_query.register(on_goals_comment_current, F.data == "goals_comment_current")
    dp.callback_query.register(on_goals_due_edit_current, F.data == "goals_due_edit_current")
    dp.callback_query.register(on_goals_schedule_current, F.data == "goals_schedule_current")
    dp.callback_query.register(on_goals_delete_current, F.data == "goals_delete_current")
    dp.message.register(on_goals_add_goal_title, GoalsFlow.waiting_goal_title)
    dp.message.register(on_goals_add_goal_due, GoalsFlow.waiting_goal_due)
    dp.message.register(on_goals_add_step_title, GoalsFlow.waiting_step_title)
    dp.message.register(on_goals_add_step_due, GoalsFlow.waiting_step_due)
    dp.message.register(on_goals_delegate_name, GoalsFlow.waiting_delegate_name)
    dp.message.register(on_goals_comment_text, GoalsFlow.waiting_comment_text)
    dp.message.register(on_goals_due_edit_text, GoalsFlow.waiting_due_edit)
