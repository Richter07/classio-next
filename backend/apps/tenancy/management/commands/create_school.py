"""Création d'une école et de son directeur, par l'équipe Classio (super-admin).

    python manage.py create_school --name "CEG Les Pylônes" --slug ceg-les-pylones \\
        --director-name "M. HOUNGBEDJI Pascal" --director-phone "01 97 00 00 10"

Affiche le code d'accès du directeur, à lui remettre en main propre.
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.academics.models import AcademicYear, SchoolSettings
from apps.accounts import access
from apps.accounts.models import Membership, User
from apps.accounts.phone import InvalidPhone, normalize_phone
from apps.tenancy.context import tenant_context
from apps.tenancy.models import School

BANDS = [{"min": 16, "label": "Très bien"}, {"min": 14, "label": "Bien"},
         {"min": 12, "label": "Assez bien"}, {"min": 10, "label": "Passable"},
         {"min": 8, "label": "Insuffisant"}, {"min": 0, "label": "Faible"}]


class Command(BaseCommand):
    help = "Crée une école, son année scolaire et le compte de son directeur."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--slug", help="Code de l'école, utilisé à la connexion.")
        parser.add_argument("--ownership", default="PRIVATE",
                            choices=School.Ownership.values)
        parser.add_argument("--city", default="")
        parser.add_argument("--director-name", required=True)
        parser.add_argument("--director-phone", required=True)
        parser.add_argument("--year", default=None, help="Ex. 2026-2027 (par défaut : en cours)")

    def handle(self, *args, **o):
        slug = o["slug"] or slugify(o["name"])[:63]
        if School.objects.filter(slug=slug).exists():
            raise CommandError(f"Le code « {slug} » est déjà pris.")
        try:
            phone = normalize_phone(o["director_phone"])
        except InvalidPhone as exc:
            raise CommandError("Numéro du directeur invalide.") from exc

        today = date.today()
        start = today.year if today.month >= 8 else today.year - 1
        label = o["year"] or f"{start}-{start + 1}"
        first = int(label[:4])

        school = School.objects.create(name=o["name"], slug=slug, ownership=o["ownership"],
                                       city=o["city"], status=School.Status.TRIAL)
        user = User.objects.filter(phone=phone).first() or User.objects.create_user(phone)
        with tenant_context(school.pk):
            SchoolSettings.objects.create(appreciation_bands=BANDS)
            AcademicYear.objects.create(label=label, starts_on=date(first, 9, 1),
                                        ends_on=date(first + 1, 7, 31), is_current=True)
            Membership.objects.create(user=user, role=Membership.Role.DIRECTOR,
                                      full_name=o["director_name"])
        self.stdout.write(self.style.SUCCESS(f"École créée : {school.name} (code : {slug})"))
        if user.has_usable_password():
            self.stdout.write("Le directeur a déjà un compte : il garde son mot de passe.")
        else:
            code = access.display_code(access.issue_code(user, school_id=school.pk))
            self.stdout.write(f"Code d'accès du directeur : {code} (valable 30 jours, "
                              "« Première connexion » sur la page du personnel)")
