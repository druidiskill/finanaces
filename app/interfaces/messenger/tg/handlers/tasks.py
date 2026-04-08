from aiogram import F, Router
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.interfaces.messenger.tg.filters import AllowedUserFilter
from app.interfaces.messenger.tg.keyboards import (
    single_action_keyboard,
    task_actions_keyboard,
    task_edit_keyboard,
    task_wallet_select_keyboard,
    tasks_list_keyboard,
)
from app.interfaces.messenger.tg.services import database
from app.interfaces.messenger.tg.states import TaskStates
from app.interfaces.messenger.tg.utils import build_task_detail_text, build_tasks_text


router = Router(name="tasks")
router.message.filter(AllowedUserFilter())
router.callback_query.filter(AllowedUserFilter())


@router.callback_query(F.data == "menu:tasks")
async def tasks_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        build_tasks_text(),
        reply_markup=tasks_list_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tasks:view:"))
async def task_view_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    task_id = int(callback.data.rsplit(":", 1)[-1])
    task = database.get_transfer_task(task_id)
    if task is None or task.status != "pending" or task.amount <= 0:
        await callback.message.edit_text(
            "🧾 Задача больше не активна.\n\n" + build_tasks_text(),
            reply_markup=tasks_list_keyboard(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        build_task_detail_text(task_id),
        reply_markup=task_actions_keyboard(task_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tasks:complete:"))
async def task_complete_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    task_id = int(callback.data.rsplit(":", 1)[-1])
    try:
        result = database.complete_transfer_task(user_id=callback.from_user.id, task_id=task_id)
    except (LookupError, ValueError) as error:
        await callback.message.edit_text(
            f"⚠️ {error}\n\n{build_tasks_text()}",
            reply_markup=tasks_list_keyboard(),
        )
        await callback.answer()
        return

    task = result["task"]
    from_wallet = result["from_wallet"]
    to_wallet = result["to_wallet"]
    await callback.message.edit_text(
        "✅ Перевод подтвержден.\n"
        f"Списано с {from_wallet.name}: {task.amount:.2f}\n"
        f"Зачислено на {to_wallet.name}: {task.amount:.2f}\n"
        f"Остаток {from_wallet.name}: {from_wallet.summ:.2f}\n"
        f"Остаток {to_wallet.name}: {to_wallet.summ:.2f}\n\n"
        f"{build_tasks_text()}",
        reply_markup=tasks_list_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tasks:edit:"))
async def task_edit_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    task_id = int(callback.data.rsplit(":", 1)[-1])
    task = database.get_transfer_task(task_id)
    if task is None or task.status != "pending" or task.amount <= 0:
        await callback.message.edit_text(
            "🧾 Задача больше не активна.\n\n" + build_tasks_text(),
            reply_markup=tasks_list_keyboard(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        build_task_detail_text(task_id) + "\n\nВыберите, что изменить:",
        reply_markup=task_edit_keyboard(task_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tasks:edit_amount:"))
async def task_edit_amount_handler(callback: CallbackQuery, state: FSMContext) -> None:
    task_id = int(callback.data.rsplit(":", 1)[-1])
    task = database.get_transfer_task(task_id)
    if task is None or task.status != "pending" or task.amount <= 0:
        await callback.message.edit_text(
            "🧾 Задача больше не активна.\n\n" + build_tasks_text(),
            reply_markup=tasks_list_keyboard(),
        )
        await callback.answer()
        return

    await state.set_state(TaskStates.waiting_for_amount)
    await state.update_data(task_id=task_id)
    await callback.message.edit_text(
        build_task_detail_text(task_id) + "\n\nВведите новую сумму перевода:",
        reply_markup=single_action_keyboard("⬅️ Назад", f"tasks:edit:{task_id}"),
    )
    await callback.answer()


@router.message(StateFilter(TaskStates.waiting_for_amount))
async def task_amount_message_handler(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    task_id = data["task_id"]
    raw_amount = (message.text or "").replace(",", ".").strip()
    try:
        amount = abs(float(raw_amount))
    except ValueError:
        await message.answer("⚠️ Введите сумму числом. Например: 1250.50")
        return

    if amount <= 0:
        await message.answer("⚠️ Сумма перевода должна быть больше нуля.")
        return

    try:
        database.update_transfer_task(
            user_id=message.from_user.id,
            task_id=task_id,
            amount=amount,
        )
    except (LookupError, ValueError) as error:
        await state.clear()
        await message.answer(
            f"⚠️ {error}\n\n{build_tasks_text()}",
            reply_markup=tasks_list_keyboard(),
        )
        return

    await state.clear()
    await message.answer(
        f"✅ Задача обновлена.\n\n{build_tasks_text()}",
        reply_markup=tasks_list_keyboard(),
    )


@router.callback_query(F.data.startswith("tasks:edit_from:"))
async def task_edit_from_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    task_id = int(callback.data.rsplit(":", 1)[-1])
    task = database.get_transfer_task(task_id)
    if task is None or task.status != "pending" or task.amount <= 0:
        await callback.message.edit_text(
            "🧾 Задача больше не активна.\n\n" + build_tasks_text(),
            reply_markup=tasks_list_keyboard(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        build_task_detail_text(task_id) + "\n\nВыберите новый кошелек списания:",
        reply_markup=task_wallet_select_keyboard(task_id=task_id, field="from", exclude_wallet_id=task.to_wallet_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tasks:edit_to:"))
async def task_edit_to_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    task_id = int(callback.data.rsplit(":", 1)[-1])
    task = database.get_transfer_task(task_id)
    if task is None or task.status != "pending" or task.amount <= 0:
        await callback.message.edit_text(
            "🧾 Задача больше не активна.\n\n" + build_tasks_text(),
            reply_markup=tasks_list_keyboard(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        build_task_detail_text(task_id) + "\n\nВыберите новый кошелек получения:",
        reply_markup=task_wallet_select_keyboard(task_id=task_id, field="to", exclude_wallet_id=task.from_wallet_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tasks:set_wallet:"))
async def task_set_wallet_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    _, _, field, task_id, wallet_id = callback.data.split(":")
    task_id_int = int(task_id)
    wallet_id_int = int(wallet_id)
    task = database.get_transfer_task(task_id_int)
    if task is None or task.status != "pending" or task.amount <= 0:
        await callback.message.edit_text(
            "🧾 Задача больше не активна.\n\n" + build_tasks_text(),
            reply_markup=tasks_list_keyboard(),
        )
        await callback.answer()
        return

    kwargs = {"from_wallet_id": wallet_id_int} if field == "from" else {"to_wallet_id": wallet_id_int}
    try:
        database.update_transfer_task(
            user_id=callback.from_user.id,
            task_id=task_id_int,
            **kwargs,
        )
    except (LookupError, ValueError) as error:
        await callback.message.edit_text(
            f"⚠️ {error}\n\n{build_task_detail_text(task_id_int)}",
            reply_markup=task_edit_keyboard(task_id_int),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"✅ Задача обновлена.\n\n{build_tasks_text()}",
        reply_markup=tasks_list_keyboard(),
    )
    await callback.answer()

