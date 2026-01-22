from aiogram.types import CallbackQuery, Message


async def edit_or_answer(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


async def delete_user_message(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
