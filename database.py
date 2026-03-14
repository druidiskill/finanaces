from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Generic, TypeVar


DEFAULT_CONST_VALUES: dict[str, tuple[float, str]] = {
    "teachers_percent": (60.0, "Доля выплат учителям"),
    "tax_physical_percent": (4.0, "Налог для доходов от физ. лиц"),
    "tax_legal_percent": (6.0, "Налог для доходов от юр. лиц"),
}


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


@dataclass(slots=True)
class Fix:
    ID: int | None = None
    active: int = 1
    name: str = ""
    summ_fix: int = 0
    date_day: int = 0
    can_finish: int = 0
    summ_finish: int | None = None
    summ_now: float = 0.0
    wallet: int = 1


@dataclass(slots=True)
class Needen:
    ID: int | None = None
    active: int = 1
    name: str = ""
    summ_need: int = 0
    summ_now: float = 0.0
    wallet: int = 1


@dataclass(slots=True)
class PastLast:
    ID: int | None = None
    active: int = 1
    name: str = ""
    parent_id: int | None = None
    percent_in_categor: int = 1


@dataclass(slots=True)
class ConstValue:
    key: str
    value: float
    description: str = ""


@dataclass(slots=True)
class HistoryEntry:
    id: int | None = None
    user_id: int = 0
    action_type: str = ""
    payload: str = ""
    created_at: str = ""


@dataclass(slots=True)
class IncomeTransaction:
    id: int | None = None
    user_id: int = 0
    wallet_id: int | None = None
    tax_mode: str = ""
    source_type: str = ""
    destination: str = ""
    amount: float = 0.0
    teachers_amount: float = 0.0
    taxes_amount: float = 0.0
    personal_amount: float = 0.0
    fix_allocated_amount: float = 0.0
    spendable_personal_amount: float = 0.0
    created_at: str = ""


@dataclass(slots=True)
class ExpenseTransaction:
    id: int | None = None
    user_id: int = 0
    category: str = ""
    amount: float = 0.0
    created_at: str = ""


@dataclass(slots=True)
class Wallet:
    ID: int | None = None
    name: str = ""
    summ: float = 0.0


@dataclass(slots=True)
class TransferTask:
    id: int | None = None
    from_wallet_id: int = 0
    to_wallet_id: int = 0
    amount: float = 0.0
    status: str = "pending"
    created_at: str = ""
    updated_at: str = ""


ModelT = TypeVar("ModelT", Fix, Needen, PastLast)


class BaseTableRepository(Generic[ModelT]):
    table_name: str
    model_type: type[ModelT]
    writable_fields: tuple[str, ...]

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    @property
    def quoted_table_name(self) -> str:
        return _quote_identifier(self.table_name)

    def _row_to_model(self, row: sqlite3.Row) -> ModelT:
        values = {field.name: row[field.name] for field in fields(self.model_type)}
        return self.model_type(**values)

    def _model_payload(self, model: ModelT) -> dict[str, object]:
        payload = asdict(model)
        return {field_name: payload[field_name] for field_name in self.writable_fields}

    def list_all(self, *, active_only: bool = False) -> list[ModelT]:
        query = f"SELECT * FROM {self.quoted_table_name}"
        params: tuple[object, ...] = ()
        if active_only:
            query += " WHERE active = ?"
            params = (1,)
        query += " ORDER BY ID"
        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_model(row) for row in rows]

    def get_by_id(self, record_id: int) -> ModelT | None:
        row = self.connection.execute(
            f"SELECT * FROM {self.quoted_table_name} WHERE ID = ?",
            (record_id,),
        ).fetchone()
        return self._row_to_model(row) if row else None

    def create(self, model: ModelT) -> ModelT:
        payload = self._model_payload(model)
        column_sql = ", ".join(_quote_identifier(column) for column in payload)
        placeholder_sql = ", ".join("?" for _ in payload)
        cursor = self.connection.execute(
            f"INSERT INTO {self.quoted_table_name} ({column_sql}) VALUES ({placeholder_sql})",
            tuple(payload.values()),
        )
        self.connection.commit()
        return self.get_by_id(int(cursor.lastrowid))  # type: ignore[return-value]

    def update(self, model: ModelT) -> ModelT:
        if model.ID is None:
            raise ValueError("ID is required for update")

        payload = self._model_payload(model)
        assignments = ", ".join(f"{_quote_identifier(column)} = ?" for column in payload)
        self.connection.execute(
            f"UPDATE {self.quoted_table_name} SET {assignments} WHERE ID = ?",
            (*payload.values(), model.ID),
        )
        self.connection.commit()
        updated = self.get_by_id(model.ID)
        if updated is None:
            raise LookupError(f"Record with ID={model.ID} was not found after update")
        return updated

    def delete(self, record_id: int) -> None:
        self.connection.execute(
            f"DELETE FROM {self.quoted_table_name} WHERE ID = ?",
            (record_id,),
        )
        self.connection.commit()

    def set_active(self, record_id: int, active: bool) -> ModelT | None:
        self.connection.execute(
            f"UPDATE {self.quoted_table_name} SET active = ? WHERE ID = ?",
            (1 if active else 0, record_id),
        )
        self.connection.commit()
        return self.get_by_id(record_id)


class FixesRepository(BaseTableRepository[Fix]):
    table_name = "fixes"
    model_type = Fix
    writable_fields = (
        "active",
        "name",
        "summ_fix",
        "date_day",
        "can_finish",
        "summ_finish",
        "summ_now",
        "wallet",
    )

    def list_pending(self, *, wallet_id: int | None = None) -> list[Fix]:
        query = f"""
            SELECT *
            FROM {self.quoted_table_name}
            WHERE active = 1
              AND summ_now < summ_fix
        """
        params: tuple[object, ...] = ()
        if wallet_id is not None:
            query += " AND wallet = ?"
            params = (wallet_id,)
        query += " ORDER BY ID"
        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_model(row) for row in rows]


class NeedenRepository(BaseTableRepository[Needen]):
    table_name = "needen"
    model_type = Needen
    writable_fields = (
        "active",
        "name",
        "summ_need",
        "summ_now",
        "wallet",
    )

    def list_active(self) -> list[Needen]:
        rows = self.connection.execute(
            f"SELECT * FROM {self.quoted_table_name} WHERE active = 1 ORDER BY ID"
        ).fetchall()
        return [self._row_to_model(row) for row in rows]


class PastLastRepository(BaseTableRepository[PastLast]):
    table_name = "past/last"
    model_type = PastLast
    writable_fields = (
        "active",
        "name",
        "parent_id",
        "percent_in_categor",
    )

    def list_children(self, parent_id: int | None) -> list[PastLast]:
        if parent_id is None:
            query = f"SELECT * FROM {self.quoted_table_name} WHERE parent_id IS NULL ORDER BY ID"
            rows = self.connection.execute(query).fetchall()
        else:
            query = f"SELECT * FROM {self.quoted_table_name} WHERE parent_id = ? ORDER BY ID"
            rows = self.connection.execute(query, (parent_id,)).fetchall()
        return [self._row_to_model(row) for row in rows]


class ConstRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_all(self) -> list[ConstValue]:
        rows = self.connection.execute("SELECT key, value, description FROM const ORDER BY key").fetchall()
        return [ConstValue(**dict(row)) for row in rows]

    def get(self, key: str) -> ConstValue | None:
        row = self.connection.execute(
            "SELECT key, value, description FROM const WHERE key = ?",
            (key,),
        ).fetchone()
        return ConstValue(**dict(row)) if row else None

    def get_required(self, key: str) -> ConstValue:
        item = self.get(key)
        if item is None:
            raise LookupError(f"Missing const value: {key}")
        return item

    def set(self, key: str, value: float, description: str | None = None) -> ConstValue:
        current = self.get(key)
        current_description = current.description if current else ""
        self.connection.execute(
            """
            INSERT INTO const (key, value, description)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, description = excluded.description
            """,
            (key, value, description if description is not None else current_description),
        )
        self.connection.commit()
        return self.get_required(key)


class HistoryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create(self, user_id: int, action_type: str, payload: dict[str, Any]) -> HistoryEntry:
        created_at = datetime.now().isoformat(timespec="seconds")
        cursor = self.connection.execute(
            """
            INSERT INTO history (user_id, action_type, payload, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, action_type, json.dumps(payload, ensure_ascii=False), created_at),
        )
        self.connection.commit()
        row = self.connection.execute(
            "SELECT id, user_id, action_type, payload, created_at FROM history WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return HistoryEntry(**dict(row))

    def list_recent(self, limit: int = 10) -> list[HistoryEntry]:
        rows = self.connection.execute(
            """
            SELECT id, user_id, action_type, payload, created_at
            FROM history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [HistoryEntry(**dict(row)) for row in rows]


class IncomeTransactionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create(
        self,
        *,
        user_id: int,
        wallet_id: int | None,
        tax_mode: str,
        source_type: str,
        destination: str,
        amount: float,
        teachers_amount: float,
        taxes_amount: float,
        personal_amount: float,
        fix_allocated_amount: float,
        spendable_personal_amount: float,
    ) -> IncomeTransaction:
        created_at = datetime.now().isoformat(timespec="seconds")
        cursor = self.connection.execute(
            """
            INSERT INTO income_transactions (
                user_id,
                wallet_id,
                tax_mode,
                source_type,
                destination,
                amount,
                teachers_amount,
                taxes_amount,
                personal_amount,
                fix_allocated_amount,
                spendable_personal_amount,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                wallet_id,
                tax_mode,
                source_type,
                destination,
                amount,
                teachers_amount,
                taxes_amount,
                personal_amount,
                fix_allocated_amount,
                spendable_personal_amount,
                created_at,
            ),
        )
        self.connection.commit()
        row = self.connection.execute(
            """
            SELECT
                id,
                user_id,
                wallet_id,
                tax_mode,
                source_type,
                destination,
                amount,
                teachers_amount,
                taxes_amount,
                personal_amount,
                fix_allocated_amount,
                spendable_personal_amount,
                created_at
            FROM income_transactions
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
        return IncomeTransaction(**dict(row))

    def list_recent(self, limit: int = 10) -> list[IncomeTransaction]:
        rows = self.connection.execute(
            """
            SELECT
                id,
                user_id,
                wallet_id,
                tax_mode,
                source_type,
                destination,
                amount,
                teachers_amount,
                taxes_amount,
                personal_amount,
                fix_allocated_amount,
                spendable_personal_amount,
                created_at
            FROM income_transactions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [IncomeTransaction(**dict(row)) for row in rows]

    def total_for_date(self, target_date: str) -> float:
        row = self.connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM income_transactions
            WHERE date(created_at) = ?
            """,
            (target_date,),
        ).fetchone()
        return float(row[0])

    def breakdown_for_date(self, target_date: str) -> dict[str, float]:
        row = self.connection.execute(
            """
            SELECT
                COALESCE(SUM(spendable_personal_amount), 0) AS personal_total,
                COALESCE(SUM(teachers_amount), 0) AS teachers_total,
                COALESCE(SUM(taxes_amount), 0) AS taxes_total
            FROM income_transactions
            WHERE date(created_at) = ?
            """,
            (target_date,),
        ).fetchone()
        return {
            "personal_total": float(row["personal_total"]),
            "teachers_total": float(row["teachers_total"]),
            "taxes_total": float(row["taxes_total"]),
        }

    def tax_breakdown_for_date(self, target_date: str) -> dict[str, Any]:
        physical_row = self.connection.execute(
            """
            SELECT COALESCE(SUM(taxes_amount), 0) AS physical_taxes_total
            FROM income_transactions
            WHERE date(created_at) = ?
              AND source_type = 'physical'
            """,
            (target_date,),
        ).fetchone()
        legal_rows = self.connection.execute(
            """
            SELECT taxes_amount, created_at
            FROM income_transactions
            WHERE date(created_at) = ?
              AND source_type = 'legal'
              AND taxes_amount > 0
            ORDER BY id
            """,
            (target_date,),
        ).fetchall()
        return {
            "physical_taxes_total": float(physical_row["physical_taxes_total"]),
            "legal_taxes_items": [
                {
                    "taxes_amount": float(row["taxes_amount"]),
                    "created_at": row["created_at"],
                }
                for row in legal_rows
            ],
        }


class ExpenseTransactionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def total_for_date(self, target_date: str) -> float:
        row = self.connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM expense_transactions
            WHERE date(created_at) = ?
            """,
            (target_date,),
        ).fetchone()
        return float(row[0])


class WalletRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_all(self) -> list[Wallet]:
        rows = self.connection.execute(
            "SELECT ID, name, summ FROM wallets ORDER BY ID"
        ).fetchall()
        return [Wallet(**dict(row)) for row in rows]

    def get_by_id(self, wallet_id: int) -> Wallet | None:
        row = self.connection.execute(
            "SELECT ID, name, summ FROM wallets WHERE ID = ?",
            (wallet_id,),
        ).fetchone()
        return Wallet(**dict(row)) if row else None

    def adjust_balance(self, wallet_id: int, amount_delta: float) -> Wallet:
        self.connection.execute(
            "UPDATE wallets SET summ = summ + ? WHERE ID = ?",
            (amount_delta, wallet_id),
        )
        self.connection.commit()
        wallet = self.get_by_id(wallet_id)
        if wallet is None:
            raise LookupError(f"Wallet with ID={wallet_id} not found")
        return wallet


class TransferTaskRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.cash_wallet_id = 1

    def list_pending(self) -> list[TransferTask]:
        rows = self.connection.execute(
            """
            SELECT id, from_wallet_id, to_wallet_id, amount, status, created_at, updated_at
            FROM transfer_tasks
            WHERE status = 'pending' AND amount > 0
            ORDER BY from_wallet_id, to_wallet_id, id
            """
        ).fetchall()
        return [TransferTask(**dict(row)) for row in rows]

    def _get_pending_pair_tasks(self, from_wallet_id: int, to_wallet_id: int) -> list[TransferTask]:
        rows = self.connection.execute(
            """
            SELECT id, from_wallet_id, to_wallet_id, amount, status, created_at, updated_at
            FROM transfer_tasks
            WHERE status = 'pending'
              AND from_wallet_id = ?
              AND to_wallet_id = ?
              AND amount > 0
            ORDER BY id
            """,
            (from_wallet_id, to_wallet_id),
        ).fetchall()
        return [TransferTask(**dict(row)) for row in rows]

    def _set_task_amount(self, task_id: int, amount: float, now: str) -> None:
        if amount <= 0:
            self.connection.execute(
                """
                UPDATE transfer_tasks
                SET amount = 0, status = 'done', updated_at = ?
                WHERE id = ?
                """,
                (now, task_id),
            )
            return

        self.connection.execute(
            """
            UPDATE transfer_tasks
            SET amount = ?, updated_at = ?
            WHERE id = ?
            """,
            (amount, now, task_id),
        )

    def _normalize_via_cash(self, now: str) -> None:
        while True:
            incoming_to_cash = self.connection.execute(
                """
                SELECT id, from_wallet_id, to_wallet_id, amount, status, created_at, updated_at
                FROM transfer_tasks
                WHERE status = 'pending'
                  AND to_wallet_id = ?
                  AND amount > 0
                ORDER BY id
                """,
                (self.cash_wallet_id,),
            ).fetchall()
            outgoing_from_cash = self.connection.execute(
                """
                SELECT id, from_wallet_id, to_wallet_id, amount, status, created_at, updated_at
                FROM transfer_tasks
                WHERE status = 'pending'
                  AND from_wallet_id = ?
                  AND amount > 0
                ORDER BY id
                """,
                (self.cash_wallet_id,),
            ).fetchall()

            if not incoming_to_cash or not outgoing_from_cash:
                break

            progress_made = False

            for incoming_row in incoming_to_cash:
                incoming_task = TransferTask(**dict(incoming_row))
                if incoming_task.amount <= 0:
                    continue

                for outgoing_row in outgoing_from_cash:
                    outgoing_task = TransferTask(**dict(outgoing_row))
                    if outgoing_task.amount <= 0:
                        continue
                    if incoming_task.from_wallet_id == outgoing_task.to_wallet_id:
                        continue

                    transfer_amount = round(min(incoming_task.amount, outgoing_task.amount), 2)
                    if transfer_amount <= 0:
                        continue

                    self._set_task_amount(incoming_task.id, round(incoming_task.amount - transfer_amount, 2), now)
                    self._set_task_amount(outgoing_task.id, round(outgoing_task.amount - transfer_amount, 2), now)

                    direct_tasks = self._get_pending_pair_tasks(
                        incoming_task.from_wallet_id,
                        outgoing_task.to_wallet_id,
                    )
                    if direct_tasks:
                        self.connection.execute(
                            """
                            UPDATE transfer_tasks
                            SET amount = amount + ?, updated_at = ?
                            WHERE id = ?
                            """,
                            (transfer_amount, now, direct_tasks[0].id),
                        )
                    else:
                        self.connection.execute(
                            """
                            INSERT INTO transfer_tasks (
                                from_wallet_id,
                                to_wallet_id,
                                amount,
                                status,
                                created_at,
                                updated_at
                            )
                            VALUES (?, ?, ?, 'pending', ?, ?)
                            """,
                            (
                                incoming_task.from_wallet_id,
                                outgoing_task.to_wallet_id,
                                transfer_amount,
                                now,
                                now,
                            ),
                        )

                    progress_made = True
                    break

                if progress_made:
                    break

            if not progress_made:
                break

    def create_or_net(self, from_wallet_id: int, to_wallet_id: int, amount: float) -> list[TransferTask]:
        if from_wallet_id == to_wallet_id or amount <= 0:
            return self.list_pending()

        remaining_amount = round(amount, 2)
        now = datetime.now().isoformat(timespec="seconds")
        reverse_tasks = self._get_pending_pair_tasks(to_wallet_id, from_wallet_id)

        for task in reverse_tasks:
            if remaining_amount <= 0:
                break
            if task.amount <= remaining_amount:
                remaining_amount = round(remaining_amount - task.amount, 2)
                self.connection.execute(
                    """
                    UPDATE transfer_tasks
                    SET amount = 0, status = 'done', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, task.id),
                )
            else:
                new_amount = round(task.amount - remaining_amount, 2)
                self.connection.execute(
                    """
                    UPDATE transfer_tasks
                    SET amount = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (new_amount, now, task.id),
                )
                remaining_amount = 0.0

        if remaining_amount > 0:
            direct_tasks = self._get_pending_pair_tasks(from_wallet_id, to_wallet_id)
            if direct_tasks:
                direct_task = direct_tasks[0]
                self.connection.execute(
                    """
                    UPDATE transfer_tasks
                    SET amount = amount + ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (remaining_amount, now, direct_task.id),
                )
            else:
                self.connection.execute(
                    """
                    INSERT INTO transfer_tasks (
                        from_wallet_id,
                        to_wallet_id,
                        amount,
                        status,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, 'pending', ?, ?)
                    """,
                    (from_wallet_id, to_wallet_id, remaining_amount, now, now),
                )

        self._normalize_via_cash(now)
        self.connection.commit()
        return self.list_pending()


class FinancesDatabase:
    def __init__(self, db_path: str | Path = "finances.db") -> None:
        self.db_path = Path(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._initialize_schema()

        self.fixes = FixesRepository(self.connection)
        self.needen = NeedenRepository(self.connection)
        self.past_last = PastLastRepository(self.connection)
        self.const = ConstRepository(self.connection)
        self.history = HistoryRepository(self.connection)
        self.income_transactions = IncomeTransactionRepository(self.connection)
        self.expense_transactions = ExpenseTransactionRepository(self.connection)
        self.wallets = WalletRepository(self.connection)
        self.transfer_tasks = TransferTaskRepository(self.connection)

    def _initialize_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS fixes (
                ID INTEGER PRIMARY KEY NOT NULL UNIQUE,
                active INTEGER DEFAULT 1 NOT NULL,
                name TEXT UNIQUE NOT NULL,
                summ_fix INTEGER NOT NULL,
                date_day INTEGER NOT NULL,
                can_finish INTEGER DEFAULT 0 NOT NULL,
                summ_finish INTEGER,
                summ_now REAL DEFAULT 0 NOT NULL,
                wallet INTEGER NOT NULL DEFAULT 1 REFERENCES wallets (ID)
            );

            CREATE TABLE IF NOT EXISTS needen (
                ID INTEGER PRIMARY KEY UNIQUE NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL,
                summ_need INTEGER NOT NULL,
                summ_now REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS "past/last" (
                ID INTEGER PRIMARY KEY NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL,
                parent_id INTEGER REFERENCES "past/last" (ID),
                percent_in_categor INTEGER DEFAULT 1 NOT NULL
            );

            CREATE TABLE IF NOT EXISTS const (
                key TEXT PRIMARY KEY NOT NULL,
                value REAL NOT NULL,
                description TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS income_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tax_mode TEXT NOT NULL,
                source_type TEXT NOT NULL,
                destination TEXT NOT NULL,
                amount REAL NOT NULL,
                teachers_amount REAL NOT NULL,
                taxes_amount REAL NOT NULL,
                personal_amount REAL NOT NULL,
                fix_allocated_amount REAL NOT NULL DEFAULT 0,
                spendable_personal_amount REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS expense_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallets (
                ID INTEGER PRIMARY KEY UNIQUE NOT NULL,
                name TEXT NOT NULL,
                summ REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS transfer_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_wallet_id INTEGER NOT NULL REFERENCES wallets (ID),
                to_wallet_id INTEGER NOT NULL REFERENCES wallets (ID),
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        income_transaction_columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(income_transactions)").fetchall()
        }
        fixes_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(fixes)").fetchall()
        }
        needen_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(needen)").fetchall()
        }
        if "wallet" not in fixes_columns:
            self.connection.execute(
                "ALTER TABLE fixes ADD COLUMN wallet INTEGER NOT NULL DEFAULT 1 REFERENCES wallets (ID)"
            )
        if "wallet" not in needen_columns:
            self.connection.execute(
                "ALTER TABLE needen ADD COLUMN wallet INTEGER NOT NULL DEFAULT 1 REFERENCES wallets (ID)"
            )
        if "fix_allocated_amount" not in income_transaction_columns:
            self.connection.execute(
                "ALTER TABLE income_transactions ADD COLUMN fix_allocated_amount REAL NOT NULL DEFAULT 0"
            )
        if "spendable_personal_amount" not in income_transaction_columns:
            self.connection.execute(
                "ALTER TABLE income_transactions ADD COLUMN spendable_personal_amount REAL NOT NULL DEFAULT 0"
            )
        if "wallet_id" not in income_transaction_columns:
            self.connection.execute(
                "ALTER TABLE income_transactions ADD COLUMN wallet_id INTEGER REFERENCES wallets (ID)"
            )
        self.connection.execute(
            """
            UPDATE income_transactions
            SET spendable_personal_amount = personal_amount - fix_allocated_amount
            WHERE spendable_personal_amount = 0
              AND personal_amount > 0
              AND fix_allocated_amount >= 0
            """
        )

        for key, (value, description) in DEFAULT_CONST_VALUES.items():
            self.connection.execute(
                """
                INSERT INTO const (key, value, description)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (key, value, description),
            )
        self.connection.commit()

    def calculate_income_distribution(
        self,
        *,
        amount: float,
        tax_mode: str,
        source_type: str,
        destination: str,
    ) -> dict[str, float]:
        teachers_percent = self.const.get_required("teachers_percent").value
        tax_key = "tax_physical_percent" if source_type == "physical" else "tax_legal_percent"
        taxes_percent = 0.0 if tax_mode == "non_taxable" else self.const.get_required(tax_key).value

        teachers_amount = round(amount * teachers_percent / 100, 2) if destination == "teachers" else 0.0
        taxes_amount = round(amount * taxes_percent / 100, 2) if tax_mode == "taxable" else 0.0
        personal_amount = round(amount - teachers_amount - taxes_amount, 2)

        return {
            "amount": round(amount, 2),
            "teachers_amount": teachers_amount,
            "taxes_amount": taxes_amount,
            "personal_amount": personal_amount,
        }

    def _next_due_date(self, date_day: int, *, now: datetime | None = None) -> datetime:
        if not 1 <= date_day <= 31:
            raise ValueError(f"Invalid date_day for fixes: {date_day}")

        reference = now or datetime.now()
        year = reference.year
        month = reference.month

        while True:
            try:
                due_date = datetime(year, month, date_day)
            except ValueError:
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                continue

            if due_date.date() >= reference.date():
                return due_date

            if month == 12:
                year += 1
                month = 1
            else:
                month += 1

    def _prioritize_by_income_wallet_type(
        self,
        items: list[Any],
        *,
        income_wallet_id: int | None,
    ) -> list[Any]:
        if income_wallet_id is None:
            return items

        preferred_cash_wallet_id = 1
        if income_wallet_id == preferred_cash_wallet_id:
            preferred_items = [item for item in items if getattr(item, "wallet", None) == preferred_cash_wallet_id]
            fallback_items = [item for item in items if getattr(item, "wallet", None) != preferred_cash_wallet_id]
        else:
            preferred_items = [item for item in items if getattr(item, "wallet", None) != preferred_cash_wallet_id]
            fallback_items = [item for item in items if getattr(item, "wallet", None) == preferred_cash_wallet_id]
        return preferred_items + fallback_items

    def get_nearest_pending_fix(
        self,
        *,
        wallet_id: int | None = None,
        income_wallet_id: int | None = None,
    ) -> Fix | None:
        pending_items = self.fixes.list_pending(wallet_id=wallet_id)
        pending_items = self._prioritize_by_income_wallet_type(
            pending_items,
            income_wallet_id=income_wallet_id,
        )
        if not pending_items:
            return None

        return min(
            pending_items,
            key=lambda item: (
                0
                if income_wallet_id is None
                else (
                    0
                    if ((income_wallet_id == 1 and item.wallet == 1) or (income_wallet_id != 1 and item.wallet != 1))
                    else 1
                ),
                self._next_due_date(item.date_day),
                item.ID if item.ID is not None else 0,
            ),
        )

    def allocate_personal_amount_to_fix(
        self,
        amount: float,
        *,
        income_wallet_id: int | None,
        restrict_wallet_id: int | None = None,
    ) -> dict[str, Any]:
        remaining_amount = round(amount, 2)
        allocations: list[dict[str, Any]] = []
        pending_tasks_before = self._capture_pending_task_map()

        while remaining_amount > 0:
            target_fix = self.get_nearest_pending_fix(
                wallet_id=restrict_wallet_id,
                income_wallet_id=income_wallet_id,
            )
            if target_fix is None:
                break

            missing_amount = round(target_fix.summ_fix - target_fix.summ_now, 2)
            if missing_amount <= 0:
                break

            allocated_amount = round(min(remaining_amount, missing_amount), 2)
            if allocated_amount <= 0:
                break
            target_fix.summ_now = round(target_fix.summ_now + allocated_amount, 2)
            updated_fix = self.fixes.update(target_fix)
            transfer_required = self._record_transfer_if_needed(
                income_wallet_id=income_wallet_id,
                target_wallet_id=updated_fix.wallet,
                allocated_amount=allocated_amount,
            )
            allocations.append(
                {
                    "allocated_amount": allocated_amount,
                    "fix": updated_fix,
                    "transfer_required": transfer_required,
                }
            )
            remaining_amount = round(remaining_amount - allocated_amount, 2)

        pending_tasks_after = self._capture_pending_task_map()

        return {
            "allocated_amount": round(sum(item["allocated_amount"] for item in allocations), 2),
            "allocations": allocations,
            "fix": allocations[-1]["fix"] if allocations else None,
            "remaining_personal_amount": remaining_amount,
            "task_changes": self._diff_pending_task_maps(pending_tasks_before, pending_tasks_after),
        }

    def _record_transfer_if_needed(
        self,
        *,
        income_wallet_id: int | None,
        target_wallet_id: int,
        allocated_amount: float,
    ) -> bool:
        transfer_required = (
            income_wallet_id is not None
            and target_wallet_id != income_wallet_id
            and allocated_amount > 0
        )
        if transfer_required:
            self.transfer_tasks.create_or_net(income_wallet_id, target_wallet_id, allocated_amount)
        return transfer_required

    def _capture_pending_task_map(self) -> dict[tuple[int, int], float]:
        return {
            (task.from_wallet_id, task.to_wallet_id): task.amount
            for task in self.transfer_tasks.list_pending()
        }

    def _diff_pending_task_maps(
        self,
        before_map: dict[tuple[int, int], float],
        after_map: dict[tuple[int, int], float],
    ) -> list[dict[str, Any]]:
        task_changes: list[dict[str, Any]] = []
        all_pairs = set(before_map) | set(after_map)
        for pair in sorted(all_pairs):
            before_amount = before_map.get(pair, 0.0)
            after_amount = after_map.get(pair, 0.0)
            delta = round(after_amount - before_amount, 2)
            if delta != 0:
                task_changes.append(
                    {
                        "from_wallet_id": pair[0],
                        "to_wallet_id": pair[1],
                        "delta_amount": delta,
                        "current_amount": after_amount,
                    }
                )
        return task_changes

    def allocate_personal_amount_to_needen(
        self,
        amount: float,
        *,
        income_wallet_id: int | None,
    ) -> dict[str, Any]:
        remaining_amount = round(amount, 2)
        allocations: list[dict[str, Any]] = []
        pending_tasks_before = self._capture_pending_task_map()

        active_items = self.needen.list_active()
        active_items = self._prioritize_by_income_wallet_type(
            active_items,
            income_wallet_id=income_wallet_id,
        )

        negative_items = [item for item in active_items if item.summ_now < 0]
        for item in negative_items:
            if remaining_amount <= 0:
                break
            needed_to_zero = round(-item.summ_now, 2)
            allocated_amount = round(min(remaining_amount, needed_to_zero), 2)
            item.summ_now = round(item.summ_now + allocated_amount, 2)
            updated_item = self.needen.update(item)
            transfer_required = self._record_transfer_if_needed(
                income_wallet_id=income_wallet_id,
                target_wallet_id=updated_item.wallet,
                allocated_amount=allocated_amount,
            )
            allocations.append(
                {
                    "allocated_amount": allocated_amount,
                    "needen": updated_item,
                    "transfer_required": transfer_required,
                }
            )
            remaining_amount = round(remaining_amount - allocated_amount, 2)

        def fill_by_level(items: list[Needen], available_amount: float) -> tuple[float, list[dict[str, Any]]]:
            local_allocations: list[dict[str, Any]] = []
            balance = round(available_amount, 2)

            def wallet_priority(item: Needen) -> int:
                if income_wallet_id is None:
                    return 0
                if income_wallet_id == 1:
                    return 0 if item.wallet == 1 else 1
                return 0 if item.wallet != 1 else 1

            current_items = [item for item in items if item.summ_need > 0 and item.summ_now < item.summ_need]

            for priority in (0, 1):
                if balance <= 0:
                    break

                priority_items = [item for item in current_items if wallet_priority(item) == priority]
                if not priority_items:
                    continue

                priority_items.sort(key=lambda item: item.summ_now / item.summ_need)
                group: list[Needen] = [priority_items[0]]
                level = group[0].summ_now / group[0].summ_need
                idx = 1

                while balance > 0 and idx < len(priority_items):
                    next_item = priority_items[idx]
                    next_level = next_item.summ_now / next_item.summ_need
                    required = round(sum((next_level - level) * item.summ_need for item in group), 2)

                    if required <= 0:
                        group.append(next_item)
                        level = next_level
                        idx += 1
                        continue

                    if balance >= required:
                        balance = round(balance - required, 2)
                        level = next_level
                        group.append(next_item)
                        idx += 1
                        continue

                    level = level + balance / sum(item.summ_need for item in group)
                    balance = 0.0
                    break

                if balance > 0:
                    max_raise = round(sum((1.0 - level) * item.summ_need for item in group), 2)
                    if max_raise > 0:
                        if balance >= max_raise:
                            balance = round(balance - max_raise, 2)
                            level = 1.0
                        else:
                            level = level + balance / sum(item.summ_need for item in group)
                            balance = 0.0

                remaining_to_apply = round(
                    min(
                        available_amount - balance,
                        sum(max(0.0, round(item.summ_need * level - item.summ_now, 2)) for item in group),
                    ),
                    2,
                )

                for index, item in enumerate(group):
                    target_amount = round(min(item.summ_need, item.summ_need * level), 2)
                    increment = round(max(0.0, target_amount - item.summ_now), 2)
                    if increment <= 0:
                        continue
                    if index == len(group) - 1:
                        increment = round(min(increment, remaining_to_apply), 2)
                    remaining_to_apply = round(remaining_to_apply - increment, 2)
                    if increment <= 0:
                        continue

                    item.summ_now = round(item.summ_now + increment, 2)
                    updated_item = self.needen.update(item)
                    transfer_required = self._record_transfer_if_needed(
                        income_wallet_id=income_wallet_id,
                        target_wallet_id=updated_item.wallet,
                        allocated_amount=increment,
                    )
                    local_allocations.append(
                        {
                            "allocated_amount": increment,
                            "needen": updated_item,
                            "transfer_required": transfer_required,
                        }
                    )

            return balance, local_allocations

        remaining_active_items = [item for item in self.needen.list_active() if item.summ_now < item.summ_need]
        while remaining_amount > 0 and remaining_active_items:
            before_remaining = remaining_amount
            remaining_amount, leveled_allocations = fill_by_level(remaining_active_items, remaining_amount)
            allocations.extend(leveled_allocations)
            if remaining_amount >= before_remaining or not leveled_allocations:
                break
            remaining_active_items = [item for item in self.needen.list_active() if item.summ_now < item.summ_need]

        pending_tasks_after = self._capture_pending_task_map()
        return {
            "allocated_amount": round(sum(item["allocated_amount"] for item in allocations), 2),
            "allocations": allocations,
            "remaining_personal_amount": remaining_amount,
            "task_changes": self._diff_pending_task_maps(pending_tasks_before, pending_tasks_after),
        }

    def create_income_transaction(
        self,
        *,
        user_id: int,
        wallet_id: int | None,
        tax_mode: str,
        source_type: str,
        destination: str,
        amount: float,
    ) -> dict[str, Any]:
        distribution = self.calculate_income_distribution(
            amount=amount,
            tax_mode=tax_mode,
            source_type=source_type,
            destination=destination,
        )
        restrict_wallet_id = 1 if source_type == "cash" else None
        fix_allocation = self.allocate_personal_amount_to_fix(
            distribution["personal_amount"],
            income_wallet_id=wallet_id,
            restrict_wallet_id=restrict_wallet_id,
        )
        needen_allocation = self.allocate_personal_amount_to_needen(
            fix_allocation["remaining_personal_amount"],
            income_wallet_id=wallet_id,
        )
        spendable_personal_amount = needen_allocation["remaining_personal_amount"]
        if wallet_id is not None:
            self.wallets.adjust_balance(wallet_id, distribution["amount"])
        transaction = self.income_transactions.create(
            user_id=user_id,
            wallet_id=wallet_id,
            tax_mode=tax_mode,
            source_type=source_type,
            destination=destination,
            amount=distribution["amount"],
            teachers_amount=distribution["teachers_amount"],
            taxes_amount=distribution["taxes_amount"],
            personal_amount=distribution["personal_amount"],
            fix_allocated_amount=fix_allocation["allocated_amount"],
            spendable_personal_amount=spendable_personal_amount,
        )
        self.history.create(
            user_id=user_id,
            action_type="income_transaction_created",
            payload={
                "transaction_id": transaction.id,
                "wallet_id": wallet_id,
                "tax_mode": tax_mode,
                "source_type": source_type,
                "destination": destination,
                "amount": distribution["amount"],
                "teachers_amount": distribution["teachers_amount"],
                "taxes_amount": distribution["taxes_amount"],
                "personal_amount": distribution["personal_amount"],
                "fix_allocated_amount": fix_allocation["allocated_amount"],
                "needen_allocated_amount": needen_allocation["allocated_amount"],
                "spendable_personal_amount": spendable_personal_amount,
                "fix_id": fix_allocation["fix"].ID if fix_allocation["fix"] else None,
            },
        )
        for allocation in fix_allocation["allocations"]:
            self.history.create(
                user_id=user_id,
                action_type="fix_allocation_created",
                payload={
                    "fix_id": allocation["fix"].ID,
                    "fix_name": allocation["fix"].name,
                    "allocated_amount": allocation["allocated_amount"],
                    "summ_now": allocation["fix"].summ_now,
                    "summ_fix": allocation["fix"].summ_fix,
                    "wallet_id": allocation["fix"].wallet,
                    "transfer_required": allocation["transfer_required"],
                },
            )
        for allocation in needen_allocation["allocations"]:
            self.history.create(
                user_id=user_id,
                action_type="needen_allocation_created",
                payload={
                    "needen_id": allocation["needen"].ID,
                    "needen_name": allocation["needen"].name,
                    "allocated_amount": allocation["allocated_amount"],
                    "summ_now": allocation["needen"].summ_now,
                    "summ_need": allocation["needen"].summ_need,
                    "wallet_id": allocation["needen"].wallet,
                    "transfer_required": allocation["transfer_required"],
                },
            )
        return {
            "transaction": transaction,
            "fix_allocation": fix_allocation,
            "needen_allocation": needen_allocation,
        }

    def get_day_totals(self, target_date: str | None = None) -> dict[str, Any]:
        day = target_date or datetime.now().date().isoformat()
        income_breakdown = self.income_transactions.breakdown_for_date(day)
        tax_breakdown = self.income_transactions.tax_breakdown_for_date(day)
        expense_total = round(self.expense_transactions.total_for_date(day), 2)
        return {
            "date": day,
            "income_total": round(income_breakdown["personal_total"], 2),
            "teachers_total": round(income_breakdown["teachers_total"], 2),
            "taxes_total": round(income_breakdown["taxes_total"], 2),
            "physical_taxes_total": round(tax_breakdown["physical_taxes_total"], 2),
            "legal_taxes_items": tax_breakdown["legal_taxes_items"],
            "expense_total": expense_total,
        }

    def get_wallet_map(self) -> dict[int, Wallet]:
        return {wallet.ID: wallet for wallet in self.wallets.list_all() if wallet.ID is not None}

    def get_financial_snapshot(self) -> dict[str, Any]:
        totals = self.get_day_totals()
        wallets = self.wallets.list_all()
        pending_tasks = self.transfer_tasks.list_pending()
        nearest_fix = self.get_nearest_pending_fix()
        return {
            "totals": totals,
            "wallets": wallets,
            "pending_tasks": pending_tasks,
            "nearest_fix": nearest_fix,
        }

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> FinancesDatabase:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
