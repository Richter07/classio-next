from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts import access
from apps.grades.bulletin import FONT_FACES, _font_only_fetcher


def _pretty_phone(phone: str) -> str:
    local = phone.removeprefix("+229")
    return " ".join(local[i:i + 2] for i in range(0, len(local), 2))


def build_letters(school, guardians, issued_by_id, reissue_activated=False) -> bytes:
    """Une page par parent : son code d'activation, ou un rappel s'il a déjà son compte.

    Émettre un code annule le précédent : les lettres déjà imprimées pour ces parents ne
    fonctionnent plus. Les parents déjà actifs ne reçoivent un code que sur demande expresse.
    """
    from weasyprint import HTML

    pages = []
    for guardian in guardians:
        children = [f"{s.first_name} {s.last_name}" for s in guardian.students.all()]
        has_account = guardian.user.has_usable_password()
        code = None
        if not has_account or reissue_activated:
            code = access.display_code(access.issue_code(guardian.user, issued_by_id, school.pk))
        pages.append({"guardian": guardian, "children": children,
                      "phone": _pretty_phone(guardian.phone),
                      "code": code, "has_account": has_account})
    html = render_to_string("access_letter.html", {
        "school": school, "pages": pages, "url": settings.PUBLIC_URL,
        "expires": access.code_expiry(), "font_faces": FONT_FACES,
        "printed_at": timezone.localdate(),
    })
    return HTML(string=html, url_fetcher=_font_only_fetcher()).write_pdf()
