"""User activity log: who did what, to which record, when and from where.

Switched on by ``ENABLE_USER_ACTIVITY_LOG``. Rows go to ``user_activity_logs``
through the same non-blocking background writer as the other log tables, so a
request never waits on it and a database problem never breaks a request.

**Data changes are captured automatically.** ``install_activity_tracking()``
hooks SQLAlchemy session events, so every service (``BaseService`` or custom)
is covered without extra code:

    flush   -> diff session.new / dirty / deleted (before/after values) -> pending
    commit  -> pending rows are queued for writing
    rollback-> pending rows are dropped: a change that never happened is never logged

    create    a new row                        changes = {field: {old: null, new}}
    update    changed columns only              changes = {field: {old, new}}
    delete    hard delete, or is_deleted -> true
    restore   is_deleted -> false

Bulk ``update(Model)...`` / ``delete(Model)...`` statements bypass the ORM's
change tracking, so they are snapshotted before (and, for updates, after) they
run and recorded per row too.

**Security events are recorded explicitly** with ``record_activity()``:

    record_activity(Activity.LOGIN, actor=f"user:{user.id}", entity=user)
    record_activity(Activity.LOGIN_FAILED, status="failed", details={"reason": "wrong_password"})

Opting a model out / ignoring noisy columns (declared on the model class):

    class RefreshToken(AuditMixin, Base):
        __activity_log__ = False                      # never audited

    class User(AuditMixin, Base):
        # updates touching only these columns are skipped
        __activity_log_ignore__ = frozenset({"last_login_on"})

Values of sensitive columns (password / secret / token ...: the same key rules
as log redaction) are stored as ``[REDACTED]``: the change is visible, the value
is not. The audit columns (created_by/on, updated_by/on) are not repeated in
``changes``: the row's actor and occurred_on already say who and when.

Limitation: rows from a rolled-back SAVEPOINT (``session.begin_nested()``) inside
a committed transaction are still recorded. The app does not use savepoints.
"""

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import event, inspect, select, tuple_
from sqlalchemy.orm import Mapper, ORMExecuteState, Session

from app.core.request_context import (
    SYSTEM_ACTOR,
    get_current_actor,
    get_request_id,
    get_request_scope,
    request_id_as_uuid,
)

logger = logging.getLogger(__name__)

ANONYMOUS_ACTOR = "anonymous"
# Bulk statements touching more rows than this are recorded as one summary row.
MAX_BULK_ROWS = 500
# Already on every row as actor / occurred_on; repeating them in `changes` is noise.
_SKIPPED_COLUMNS = frozenset({"id", "created_by", "created_on", "updated_by", "updated_on"})
_PENDING_KEY = "user_activity_pending"


class Activity(StrEnum):
    # data changes (automatic)
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"
    # security events (explicit)
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_ISSUED = "token_issued"  # API client (client credentials)
    CLIENT_AUTH_FAILED = "client_auth_failed"
    SESSION_REVOKED = "session_revoked"  # refresh-token reuse: likely a stolen token
    ACCESS_DENIED = "access_denied"  # any 403


def _sink():
    from app.core.logging import db_sink  # lazy: avoids an import cycle; patchable in tests

    return db_sink.user_activity_log_sink


def _enabled() -> bool:
    return _sink().running


# ------------------------------------------------------------------ row building
def _split_actor(actor: str) -> tuple[str, str | None]:
    kind, sep, ident = actor.partition(":")
    if sep and kind in ("user", "service"):
        return kind, ident
    return (ANONYMOUS_ACTOR if actor == ANONYMOUS_ACTOR else "system"), None


def _cut(value: Any, length: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= length else text[: length - 3] + "..."


def _json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _build_row(
    action: str,
    *,
    status: str = "success",
    entity_type: str | None = None,
    entity_id: Any = None,
    changes: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    actor: str | None = None,
):
    from app.core.logging.request_info import client_ip, route_info
    from app.schemas.user_activity_log import UserActivityLogCreate

    scope = get_request_scope()
    actor = actor or get_current_actor()
    if actor == SYSTEM_ACTOR and scope is not None:
        actor = ANONYMOUS_ACTOR  # inside an HTTP request without a valid token
    actor_type, actor_id = _split_actor(actor)

    method = route = ip = user_agent = None
    if scope is not None:
        method = scope.get("method")
        route = route_info(scope)["route"]
        ip = client_ip(scope)
        for key, value in scope.get("headers") or []:
            if key.lower() == b"user-agent":
                user_agent = value.decode("latin-1")
                break

    return UserActivityLogCreate(
        occurred_on=datetime.now(UTC),
        actor=_cut(actor, 255),
        actor_type=actor_type,
        actor_id=_cut(actor_id, 64),
        action=str(action),
        status=status,
        entity_type=_cut(entity_type, 64),
        entity_id=_cut(entity_id, 64),
        changes=_json_value(changes) if changes else None,
        details=_json_value(details) if details else None,
        request_id=request_id_as_uuid(get_request_id()),
        method=_cut(method, 16),
        route=_cut(route, 512),
        ip_address=_cut(ip, 64),
        user_agent=_cut(user_agent, 512),
        created_by=_cut(actor, 255),
    )


def record_activity(
    action: str,
    *,
    status: str = "success",
    entity: Any = None,
    entity_type: str | None = None,
    entity_id: Any = None,
    details: dict[str, Any] | None = None,
    actor: str | None = None,
) -> None:
    """Record one security event now (not tied to a transaction). Never raises.

    ``entity`` (an ORM object) fills entity_type / entity_id. ``actor`` defaults to
    the current caller; pass it when the caller is only known by the event itself
    (e.g. ``user:<id>`` on a successful login).
    """
    try:
        if not _enabled():
            return
        if entity is not None:
            mapper = inspect(entity).mapper
            entity_type, entity_id = _table(mapper), _pk(mapper, entity)
        _sink().enqueue(
            _build_row(
                action,
                status=status,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details,
                actor=actor,
            )
        )
    except Exception:  # auditing must never break the real work
        logger.warning("Could not record user activity %s", action, exc_info=True)


# ----------------------------------------------------------------- ORM capture
def _audited(mapper: Mapper | None) -> bool:
    return mapper is not None and getattr(mapper.class_, "__activity_log__", True)


def _ignored(mapper: Mapper) -> frozenset[str]:
    return getattr(mapper.class_, "__activity_log_ignore__", frozenset())


def _table(mapper: Mapper) -> str:
    return mapper.local_table.name


def _pk(mapper: Mapper, obj: Any) -> str | None:
    values = mapper.primary_key_from_instance(obj)
    if any(v is None for v in values):
        return None
    return ",".join(str(v) for v in values)


def _safe(field: str, value: Any) -> Any:
    from app.core.redaction import REDACTED, get_redactor

    if value is not None and get_redactor().is_sensitive_key(field):
        return REDACTED
    return value


def _fields(mapper: Mapper) -> Iterable[str]:
    skipped = _SKIPPED_COLUMNS | _ignored(mapper)
    return (a.key for a in mapper.column_attrs if a.key not in skipped)


def _snapshot(mapper: Mapper, obj: Any, side: str) -> dict[str, Any]:
    """All non-null values as {field: {old|new: value}}, for creates and deletes."""
    other = "new" if side == "old" else "old"
    loaded = inspect(obj).dict  # never getattr: an unloaded column would emit SQL mid-flush
    values = {}
    for key in _fields(mapper):
        value = loaded.get(key)
        if value is not None:
            values[key] = {side: _safe(key, value), other: None}
    return values


def _diff(mapper: Mapper, obj: Any) -> dict[str, Any]:
    state = inspect(obj)
    changes = {}
    for key in _fields(mapper):
        history = state.attrs[key].history
        if not history.has_changes():
            continue
        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else None
        if old != new:
            changes[key] = {"old": _safe(key, old), "new": _safe(key, new)}
    return changes


def _pending(session: Session) -> list:
    return session.info.setdefault(_PENDING_KEY, [])


def _change_action(changes: dict[str, Any]) -> Activity:
    deleted = changes.get("is_deleted")
    if deleted is not None:
        return Activity.DELETE if deleted["new"] else Activity.RESTORE
    return Activity.UPDATE


def _after_flush(session: Session, _flush_context: Any) -> None:
    try:
        if not _enabled():
            return
        rows = []
        for obj in session.new:
            mapper = inspect(obj).mapper
            if _audited(mapper):
                rows.append(
                    _build_row(
                        Activity.CREATE,
                        entity_type=_table(mapper),
                        entity_id=_pk(mapper, obj),
                        changes=_snapshot(mapper, obj, "new"),
                    )
                )
        for obj in session.dirty:
            mapper = inspect(obj).mapper
            if not _audited(mapper) or not session.is_modified(obj):
                continue
            changes = _diff(mapper, obj)
            if changes:  # only ignored / audit columns changed -> nothing to say
                rows.append(
                    _build_row(
                        _change_action(changes),
                        entity_type=_table(mapper),
                        entity_id=_pk(mapper, obj),
                        changes=changes,
                    )
                )
        for obj in session.deleted:
            mapper = inspect(obj).mapper
            if _audited(mapper):
                rows.append(
                    _build_row(
                        Activity.DELETE,
                        entity_type=_table(mapper),
                        entity_id=_pk(mapper, obj),
                        changes=_snapshot(mapper, obj, "old"),
                    )
                )
        _pending(session).extend(rows)
    except Exception:
        logger.warning("Could not capture user activity for a flush", exc_info=True)


def _row_dicts(session: Session, mapper: Mapper, where: Any) -> list[dict[str, Any]] | None:
    """Current rows matching a bulk statement's WHERE (None if there are too many)."""
    table = mapper.local_table
    query = select(*table.columns).limit(MAX_BULK_ROWS + 1)
    if where is not None:
        query = query.where(where)
    rows = [dict(r._mapping) for r in session.execute(query)]
    return None if len(rows) > MAX_BULK_ROWS else rows


def _bulk_pk(mapper: Mapper, row: dict[str, Any]) -> str:
    return ",".join(str(row[c.key]) for c in mapper.local_table.primary_key.columns)


def _do_orm_execute(state: ORMExecuteState) -> Any:
    """Record bulk UPDATE / DELETE statements, which skip the flush-based capture."""
    if not (state.is_update or state.is_delete) or not _audited(state.bind_mapper):
        return None
    try:
        if not _enabled():
            return None
        mapper = state.bind_mapper
        where = state.statement.whereclause
        before = _row_dicts(state.session, mapper, where)
    except Exception:
        logger.warning("Could not snapshot a bulk statement", exc_info=True)
        return None

    result = state.invoke_statement()  # run it now, so the "after" values can be read

    try:
        pending, table = _pending(state.session), _table(mapper)
        action = Activity.DELETE if state.is_delete else Activity.UPDATE
        if before is None:
            pending.append(
                _build_row(
                    action, entity_type=table, details={"bulk": True, "rows": f">{MAX_BULK_ROWS}"}
                )
            )
            return result
        skipped = _SKIPPED_COLUMNS | _ignored(mapper)
        after: dict[str, dict[str, Any]] = {}
        if state.is_update and before:
            pk_cols = list(mapper.local_table.primary_key.columns)
            ids = [tuple(r[c.key] for c in pk_cols) for r in before]
            query = select(*mapper.local_table.columns).where(tuple_(*pk_cols).in_(ids))
            after = {
                _bulk_pk(mapper, dict(r._mapping)): dict(r._mapping)
                for r in state.session.execute(query)
            }
        for old in before:
            key = _bulk_pk(mapper, old)
            if state.is_delete:
                changes = {
                    k: {"old": _safe(k, v), "new": None}
                    for k, v in old.items()
                    if k not in skipped and v is not None
                }
                pending.append(
                    _build_row(action, entity_type=table, entity_id=key, changes=changes)
                )
                continue
            new = after.get(key, {})
            changes = {
                k: {"old": _safe(k, v), "new": _safe(k, new.get(k))}
                for k, v in old.items()
                if k not in skipped and k in new and new[k] != v
            }
            if changes:
                pending.append(
                    _build_row(
                        _change_action(changes), entity_type=table, entity_id=key, changes=changes
                    )
                )
    except Exception:
        logger.warning("Could not capture user activity for a bulk statement", exc_info=True)
    return result


def _after_commit(session: Session) -> None:
    rows = session.info.pop(_PENDING_KEY, None)
    if not rows:
        return
    sink = _sink()
    for row in rows:
        sink.enqueue(row)


def _after_soft_rollback(session: Session, previous_transaction: Any) -> None:
    # Any rollback of the session's own transaction: those changes never happened.
    if not previous_transaction.nested:
        session.info.pop(_PENDING_KEY, None)


_installed = False


def install_activity_tracking() -> None:
    """Hook the session events (idempotent). Rows are only built while the sink runs."""
    global _installed
    if _installed:
        return
    event.listen(Session, "after_flush", _after_flush)
    event.listen(Session, "do_orm_execute", _do_orm_execute)
    event.listen(Session, "after_commit", _after_commit)
    event.listen(Session, "after_soft_rollback", _after_soft_rollback)
    _installed = True
