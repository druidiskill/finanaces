from aiogram.utils.keyboard import InlineKeyboardBuilder

from .utils import status_emoji


def build_main_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💼 Учет доходов/расходов", callback_data="section_finance")
    kb.button(text="🎯 Цели", callback_data="section_goals")
    kb.button(text="⏳ Тайм-менеджмент", callback_data="section_time")
    kb.adjust(1)
    return kb.as_markup()


def build_cancel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="cancel")
    return kb.as_markup()


def build_comment_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🚫 Без комментариев", callback_data="comment_skip")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_category_kb(categories: list[str], add_label: str, show_done: bool):
    kb = InlineKeyboardBuilder()
    for idx, category in enumerate(categories):
        kb.button(text=f"📁 {category}", callback_data=f"cat_idx:{idx}")
    kb.button(text=add_label, callback_data="cat_add")
    if show_done:
        kb.button(text="✅ Готово", callback_data="cat_done")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_summary_kind_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Доходы", callback_data="sum_kind:income")
    kb.button(text="💸 Расходы", callback_data="sum_kind:expense")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_summary_period_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Сегодня", callback_data="sum_period:today")
    kb.button(text="🗓️ 7 дней", callback_data="sum_period:7d")
    kb.button(text="🗓️ 30 дней", callback_data="sum_period:30d")
    kb.button(text="🧭 Диапазон", callback_data="sum_period:range")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_summary_category_kb(categories: list[str], show_done: bool, show_all: bool):
    kb = InlineKeyboardBuilder()
    for idx, category in enumerate(categories):
        kb.button(text=f"📁 {category}", callback_data=f"sum_cat_idx:{idx}")
    if show_done:
        kb.button(text="✅ Готово", callback_data="sum_cat_done")
    if show_all:
        kb.button(text="📦 Все категории", callback_data="sum_cat_all")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def build_goals_root_kb(items: list[dict]):
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(text=item["label"], callback_data=f"goals_open:{item['id']}")
    kb.button(text="➕🎯 Добавить цель", callback_data="goals_add_goal")
    kb.button(text="🔙 Назад", callback_data="section_back")
    kb.adjust(1)
    return kb.as_markup()


def build_goals_children_kb(items: list[dict], parent_id: str, show_add_step: bool):
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(text=item["label"], callback_data=f"goals_open:{item['id']}")
    if show_add_step:
        kb.button(text="➕🧩 Добавить этап", callback_data="goals_add_step_current")
    kb.button(text="💬 Комментарий", callback_data="goals_comment_current")
    kb.button(text="🗑️ Удалить", callback_data="goals_delete_current")
    kb.button(text="🔙 Назад", callback_data=f"goals_back:{parent_id}")
    kb.adjust(1)
    return kb.as_markup()


def build_goals_leaf_kb(parent_id: str, status: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Делегировать", callback_data="goals_delegate_current")
    kb.button(text="🗓️ В расписание", callback_data="goals_schedule_current")
    kb.button(text=f"{status_emoji(status)} Статус", callback_data="goals_status_current")
    kb.button(text="💬 Комментарий", callback_data="goals_comment_current")
    kb.button(text="➕🧩 Добавить этап", callback_data="goals_add_step_current")
    kb.button(text="🗑️ Удалить", callback_data="goals_delete_current")
    kb.button(text="🔙 Назад", callback_data=f"goals_back:{parent_id}")
    kb.adjust(1)
    return kb.as_markup()


def build_goal_status_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 В планах", callback_data="goals_status_set:todo")
    kb.button(text="⚙️ В процессе", callback_data="goals_status_set:in_progress")
    kb.button(text="✅ Выполнено", callback_data="goals_status_set:done")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()
