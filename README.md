finances bot

Telegram-бот для учета доходов/расходов с записью в Google Sheets.

Базовые столбцы в таблице:
1) timestamp
2) kind (income/expense)
3) amount
4) comment
5) user_id

Подготовка:
1) Создать сервисный аккаунт Google и выдать доступ к таблице.
2) Создать `.env` по образцу `.env.example`.
3) Установить зависимости.

Запуск:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
