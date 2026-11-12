from pathlib import Path

from django.template.loader import render_to_string
from django.utils import timezone

# Noto Sans réduite aux caractères latins (licence SIL OFL) : découper une petite police est
# environ trois fois plus rapide que DejaVu, sans HarfBuzz-subset sur le serveur.
FONTS_DIR = (Path(__file__).parent / "fonts").resolve()
FONT_FACES = "".join(
    f'@font-face {{ font-family: "Classio"; font-weight: {weight}; '
    f'src: url("{(FONTS_DIR / f"noto-sans-latin-{weight}-normal.woff").as_uri()}"); }}'
    for weight in (400, 700)
)

KIND_LABELS = {"HOMEWORK": "Devoir", "QUIZ": "Interrogation", "EXAM": "Composition"}


def _font_only_fetcher():
    """Rien d'autre que nos deux polices : refuser tout autre chargement ferme la porte à la
    lecture de fichiers du serveur et aux requêtes vers le réseau interne (SSRF)."""
    from urllib.parse import unquote, urlparse

    from weasyprint.urls import URLFetcher

    class FontOnlyFetcher(URLFetcher):
        def fetch(self, url, headers=None):
            parsed = urlparse(url)
            path = Path(unquote(parsed.path)).resolve()
            if parsed.scheme != "file" or path.parent != FONTS_DIR or path.suffix != ".woff":
                raise ValueError(f"Chargement refusé : {url}")
            return super().fetch(url, headers)

    return FontOnlyFetcher(allowed_protocols=["file"])


def ordinal(rank: int | None, tied: bool) -> str:
    if rank is None:
        return "—"
    suffix = "er" if rank == 1 else "e"
    return f"{rank}{suffix}" + (" ex æquo" if tied else "")


def fr(value, decimals=2) -> str:
    """12.5 -> « 12,50 » ; None -> « — ». Les chiffres sont mis en forme une fois pour toutes :
    un bulletin publié est conservé tel quel."""
    if value is None:
        return "—"
    return f"{value:.{decimals}f}".replace(".", ",")


def coef(value) -> str:
    """Coefficient ou barème sans zéros inutiles : 2 -> « 2 », 1.5 -> « 1,5 », 20.00 -> « 20 »."""
    from decimal import Decimal

    text = format(Decimal(str(value)).normalize(), "f")
    return text.replace(".", ",")


def build_pages(results, classroom, period, student_ids=None) -> list[dict]:
    """Une page par élève, en données simples (JSON) : c'est ce qui est figé à la publication."""
    homework_columns = max(2, max((len(d.homeworks) for s in results.students
                                   for d in s.subject_details.values()), default=0))
    exam_columns = max((len(d.exams) for s in results.students
                        for d in s.subject_details.values()), default=0)
    ranked = results.ranked_size
    pages = []
    for s in results.students:
        if student_ids is not None and s.enrollment.student_id not in student_ids:
            continue
        rows, total_coef, total_weighted = [], 0, 0
        for line in results.subjects:
            key = line.class_subject.pk
            average = s.subject_averages.get(key)
            detail = s.subject_details.get(key)
            rank, tied = s.subject_ranks.get(key, (None, False))
            weighted = results.rules.round(average * line.coefficient) if average is not None \
                else None
            if average is not None:
                total_coef += line.coefficient
                total_weighted += weighted
            pad = lambda values, n: ["Abs" if v is None else fr(v) for v in values] + ["—"] * (n - len(values))  # noqa: E731,E501
            rows.append({
                "id": str(key),
                "subject": line.class_subject.subject.name,
                "teacher": line.class_subject.teacher.full_name
                if line.class_subject.teacher else "",
                "quiz": fr(detail.quiz_average if detail else None),
                "homeworks": pad(detail.homeworks if detail else [], homework_columns),
                "exams": pad(detail.exams if detail else [], exam_columns),
                "average": fr(average),
                "coefficient": coef(line.coefficient),
                "weighted": fr(weighted),
                "rank": ordinal(rank, tied),
                "class_average": fr(line.class_average),
                "appreciation": results.rules.appreciation(average),
            })
        student = s.enrollment.student
        pages.append({
            "student_id": str(student.pk),
            "student": {"last_name": student.last_name, "first_name": student.first_name,
                        "matricule": student.matricule},
            "classroom": classroom.name,
            "period": period.name,
            "year": period.year.label,
            "homework_columns": homework_columns,
            # Colonnes avant « Coef. » : matière, moy. interro, devoirs, compositions, moyenne.
            "total_span": 3 + homework_columns + exam_columns,
            "exam_columns": exam_columns,
            "rows": rows,
            "total_coefficients": coef(total_coef),
            "total_weighted": fr(total_weighted if total_coef else None),
            "general": fr(s.general),
            "general_value": str(s.general) if s.general is not None else None,
            "max_score": coef(results.rules.max_score),
            "rank": ordinal(s.rank, s.tied),
            "rank_value": s.rank,
            "tied": s.tied,
            "ranked_size": ranked,
            "appreciation": s.appreciation,
            "class_average": fr(results.class_average),
            "highest": fr(results.highest),
            "lowest": fr(results.lowest),
        })
    return pages


CACHE_SECONDS = 7 * 24 * 3600


def render_pdf(school, pages: list[dict], draft=False) -> bytes:
    """Le PDF est mis en cache sous l'empreinte de son HTML : un second téléchargement est
    immédiat, et la moindre note modifiée change l'empreinte, donc le PDF."""
    import hashlib

    from django.core.cache import cache
    from weasyprint import HTML

    html = render_to_string("bulletin.html", {
        "school": school, "pages": pages, "printed_at": timezone.localdate(),
        "font_faces": FONT_FACES, "draft": draft,
    })
    key = "bulletin:" + hashlib.sha256(html.encode()).hexdigest()
    if (pdf := cache.get(key)) is not None:
        return pdf
    pdf = HTML(string=html, url_fetcher=_font_only_fetcher()).write_pdf()
    cache.set(key, pdf, CACHE_SECONDS)
    return pdf
