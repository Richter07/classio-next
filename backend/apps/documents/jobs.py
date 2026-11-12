"""Documents longs à produire (bulletins d'une classe, lettres d'accès) : générés par Celery, gardés
une heure dans Redis, téléchargés quand ils sont prêts. Une requête HTTP n'attend jamais la fin
d'une génération de plusieurs dizaines de secondes.

L'état d'un travail mémorise son auteur et son école : personne d'autre ne peut le télécharger.
"""

import uuid

from django.core.cache import cache
from django.db import transaction

TTL = 60 * 60


def _key(job_id, suffix=""):
    return f"job:{job_id}{suffix}"


def start(task, *, user_id, school_id, filename, **kwargs) -> str:
    job_id = str(uuid.uuid4())
    cache.set(_key(job_id), {"status": "pending", "user_id": str(user_id),
                             "school_id": str(school_id), "filename": filename}, TTL)
    # Après validation de la transaction : le travail doit voir les données de la requête.
    transaction.on_commit(lambda: task.delay(job_id=job_id, user_id=str(user_id),
                                             school_id=str(school_id), **kwargs))
    return job_id


def finish(job_id, pdf: bytes | None = None, error: str | None = None) -> None:
    state = cache.get(_key(job_id)) or {}
    if error:
        state.update(status="failed", error=error)
    else:
        cache.set(_key(job_id, ":pdf"), pdf, TTL)
        state.update(status="done")
    cache.set(_key(job_id), state, TTL)


def state_for(job_id, user_id, school_id) -> dict | None:
    state = cache.get(_key(job_id))
    if not state or state["user_id"] != str(user_id) or state["school_id"] != str(school_id):
        return None
    return state


def pdf_for(job_id) -> bytes | None:
    return cache.get(_key(job_id, ":pdf"))
