"""Contexte d'exécution lu par les politiques RLS de PostgreSQL.

Toute lecture ou écriture de données d'école passe par ``tenant_context``, y compris dans
les tâches Celery et les commandes de gestion. Sans contexte, la base ne renvoie aucune ligne.

Les valeurs sont posées avec ``set_config(..., is_local => true)`` : elles meurent avec la
transaction, ce qui évite toute fuite d'une requête à l'autre sur une connexion réutilisée.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from django.db import connection, transaction


@dataclass(frozen=True)
class TenantState:
    school_id: UUID | None = None
    user_id: UUID | None = None
    is_platform: bool = False


_state: ContextVar[TenantState | None] = ContextVar("classio_tenant", default=None)


def current_state() -> TenantState | None:
    return _state.get()


def current_school_id() -> UUID | None:
    state = _state.get()
    return state.school_id if state else None


def _apply(state: TenantState) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT set_config('app.school_id', %s, true),
                   set_config('app.user_id', %s, true),
                   set_config('app.is_platform', %s, true)
            """,
            [
                str(state.school_id) if state.school_id else "",
                str(state.user_id) if state.user_id else "",
                "on" if state.is_platform else "off",
            ],
        )


@contextmanager
def tenant_context(
    school_id: UUID | None = None,
    user_id: UUID | None = None,
    is_platform: bool = False,
) -> Iterator[TenantState]:
    """Ouvre une transaction portant le contexte, et restaure le précédent en sortie."""
    previous = _state.get()
    state = TenantState(school_id, user_id, is_platform)
    token = _state.set(state)
    try:
        with transaction.atomic():
            _apply(state)
            yield state
    finally:
        _state.reset(token)
        # Un set_config local survit à la libération d'un savepoint : dans une transaction
        # englobante, il faut revenir à l'état précédent, y compris à l'absence de contexte.
        if connection.in_atomic_block and not connection.needs_rollback:
            _apply(previous or TenantState())
