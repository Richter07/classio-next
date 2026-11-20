import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", "3"))
# Les documents longs passent par Celery : une requête ne doit jamais approcher ce délai.
timeout = 60
graceful_timeout = 30
keepalive = 5
# Battement de cœur des workers en mémoire : sur le /tmp d'un conteneur Docker, l'écriture
# peut bloquer, et Gunicorn tue alors des workers sains (« WORKER TIMEOUT », erreurs 502).
worker_tmp_dir = "/dev/shm"
# Recycle les workers pour contenir la mémoire de WeasyPrint.
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
# Pas d'en-tête Referer ni de paramètres de requête dans les journaux d'accès.
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(M)sms'


def post_worker_init(worker):
    """Préchauffe WeasyPrint : sans cela, le premier bulletin demandé après un redémarrage
    prend une dizaine de secondes (chargement des polices et de la configuration)."""
    try:
        from weasyprint import HTML

        from apps.grades.bulletin import FONT_FACES, _font_only_fetcher

        HTML(string=f"<style>{FONT_FACES} body{{font-family:Classio}}</style><b>é</b>é",
             url_fetcher=_font_only_fetcher()).write_pdf()
    except Exception as exc:  # le préchauffage ne doit jamais empêcher le démarrage
        worker.log.warning("Préchauffage WeasyPrint impossible : %s", exc)
