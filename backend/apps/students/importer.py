"""Import des élèves et des parents depuis Excel ou CSV.

Deux temps : ``check`` contrôle chaque ligne et produit un rapport, sans rien écrire ;
``apply`` crée seulement les lignes valides, après validation humaine.
"""

import csv
import io
import unicodedata
from datetime import date, datetime

from django.db import transaction

from apps.academics.models import AcademicYear, Classroom
from apps.accounts.models import User
from apps.accounts.phone import InvalidPhone, normalize_phone

from .models import Enrollment, Guardian, Guardianship, Student

MAX_ROWS = 3000
MAX_BYTES = 2 * 1024 * 1024

COLUMNS = {
    "matricule": ["matricule", "numero matricule", "n matricule"],
    "last_name": ["nom", "nom eleve", "nom de l eleve"],
    "first_name": ["prenom", "prenoms", "prenom s", "prenom eleve", "prenoms eleve"],
    "birth_date": ["date de naissance", "date naissance", "ne le", "naissance"],
    "sex": ["sexe", "genre"],
    "classroom": ["classe"],
    "guardian_name": ["nom du parent", "nom parent", "parent", "nom et prenoms du parent"],
    "guardian_phone": ["telephone du parent", "telephone parent", "tel parent", "telephone",
                       "contact parent", "numero du parent"],
}
REQUIRED = ["matricule", "last_name", "first_name", "birth_date", "classroom", "guardian_phone"]
LABELS = {"matricule": "Matricule", "last_name": "Nom", "first_name": "Prénom(s)",
          "birth_date": "Date de naissance", "sex": "Sexe", "classroom": "Classe",
          "guardian_name": "Nom du parent", "guardian_phone": "Téléphone du parent"}


class ImportFileError(ValueError):
    pass


def _key(text) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join("".join(c if c.isalnum() else " " for c in text.lower()).split())


def _read(name: str, content: bytes) -> list[list]:
    if len(content) > MAX_BYTES:
        raise ImportFileError("Fichier trop volumineux (2 Mo au plus).")
    if name.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        try:
            sheet = load_workbook(io.BytesIO(content), read_only=True, data_only=True).active
        except Exception as exc:
            raise ImportFileError("Fichier Excel illisible.") from exc
        rows = []
        for row in sheet.iter_rows(values_only=True):
            rows.append(list(row))
            if len(rows) > MAX_ROWS + 1:
                raise ImportFileError(f"{MAX_ROWS} lignes au plus par import.")
        return rows
    if name.lower().endswith(".csv"):
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=";,\t")
        rows = list(csv.reader(io.StringIO(text), dialect))
        if len(rows) > MAX_ROWS + 1:
            raise ImportFileError(f"{MAX_ROWS} lignes au plus par import.")
        return rows
    raise ImportFileError("Format accepté : .xlsx ou .csv")


def _map_header(header: list) -> dict:
    mapping = {}
    for index, cell in enumerate(header):
        key = _key(cell)
        for field, aliases in COLUMNS.items():
            if key in aliases and field not in mapping:
                mapping[field] = index
    missing = [LABELS[f] for f in REQUIRED if f not in mapping]
    if missing:
        raise ImportFileError("Colonnes manquantes : " + ", ".join(missing)
                              + ". Utilisez le modèle fourni.")
    return mapping


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value).split())


def check(name: str, content: bytes) -> dict:
    rows = _read(name, content)
    if not rows:
        raise ImportFileError("Le fichier est vide.")
    mapping = _map_header(rows[0])
    year = AcademicYear.objects.filter(is_current=True).first()
    if year is None:
        raise ImportFileError("Aucune année scolaire en cours n'est configurée.")
    classrooms = {_key(c.name): c for c in Classroom.objects.filter(year=year)}
    known_matricules = set(Student.objects.values_list("matricule", flat=True))
    known_phones = set(Guardian.objects.values_list("phone", flat=True))
    seen, report_rows = set(), []
    new_phones = set()

    for line_no, raw in enumerate(rows[1:], start=2):
        values = {f: raw[i] if i < len(raw) else None for f, i in mapping.items()}
        if not any(_text(v) for v in values.values()):
            continue
        errors = []
        data = {f: _text(values.get(f)) for f in COLUMNS}
        for field in REQUIRED:
            if not data[field]:
                errors.append(f"{LABELS[field]} manquant.")
        born = _parse_date(values.get("birth_date"))
        if data["birth_date"] and born is None:
            errors.append("Date de naissance illisible (format attendu : jj/mm/aaaa).")
        elif born and not (1990 <= born.year <= date.today().year - 2):
            errors.append("Date de naissance improbable.")
        data["birth_date"] = born.isoformat() if born else data["birth_date"]
        sex = data["sex"][:1].upper()
        if data["sex"] and sex not in ("F", "M"):
            errors.append("Sexe attendu : F ou M.")
        data["sex"] = sex if sex in ("F", "M") else ""
        if data["classroom"]:
            classroom = classrooms.get(_key(data["classroom"]))
            if classroom is None:
                errors.append(f"Classe « {data['classroom']} » inconnue cette année.")
            else:
                data["classroom"], data["classroom_id"] = classroom.name, str(classroom.pk)
        if data["guardian_phone"]:
            try:
                data["guardian_phone"] = normalize_phone(data["guardian_phone"])
                if data["guardian_phone"] not in known_phones:
                    new_phones.add(data["guardian_phone"])
            except InvalidPhone:
                errors.append("Téléphone du parent invalide.")
        if data["matricule"]:
            if data["matricule"] in known_matricules:
                errors.append("Ce matricule existe déjà dans l'école.")
            elif data["matricule"] in seen:
                errors.append("Matricule en double dans le fichier.")
            seen.add(data["matricule"])
        report_rows.append({"line": line_no, "data": data, "errors": errors})

    valid = [r for r in report_rows if not r["errors"]]
    return {
        "total": len(report_rows), "valid": len(valid),
        "invalid": len(report_rows) - len(valid),
        "new_guardians": len({r["data"]["guardian_phone"] for r in valid}
                             & new_phones),
        "rows": report_rows,
    }


@transaction.atomic
def apply(report: dict) -> dict:
    year = AcademicYear.objects.get(is_current=True)
    created = guardians_created = 0
    new_guardians = []
    for row in report["rows"]:
        if row["errors"]:
            continue
        data = row["data"]
        student = Student.objects.create(
            matricule=data["matricule"], last_name=data["last_name"].upper(),
            first_name=data["first_name"], birth_date=date.fromisoformat(data["birth_date"]),
            sex=data["sex"],
        )
        Enrollment.objects.create(student=student, classroom_id=data["classroom_id"], year=year)
        guardian, is_new = link_guardian(student, data["guardian_phone"], data["guardian_name"])
        if is_new:
            guardians_created += 1
            new_guardians.append(guardian)
        created += 1
    return {"students": created, "guardians": guardians_created,
            "new_guardians": new_guardians}


def link_guardian(student, phone: str, name: str):
    guardian = Guardian.objects.filter(phone=phone).first()
    is_new = guardian is None
    if is_new:
        user = User.objects.filter(phone=phone).first() or User.objects.create_user(phone)
        guardian = Guardian.objects.create(user=user, phone=phone,
                                           full_name=name or "Parent")
    Guardianship.objects.get_or_create(guardian=guardian, student=student)
    return guardian, is_new


def template_workbook() -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    year = AcademicYear.objects.filter(is_current=True).first()
    classes = [c.name for c in Classroom.objects.filter(year=year).order_by("name")]
    wb = Workbook()
    ws = wb.active
    ws.title = "Élèves"
    headers = [LABELS[f] for f in COLUMNS]
    ws.append(headers)
    example = classes[0] if classes else "6e A"
    ws.append(["2026-001", "ADJOVI", "Koffi Jean", "12/03/2014", "M", example,
               "ADJOVI Mathieu", "01 97 00 00 00"])
    ws.append(["2026-002", "HOUNKPATIN", "Awa", "05/11/2013", "F", example,
               "HOUNKPATIN Rose", "96 00 00 00"])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0E5A43")
    for column, width in zip("ABCDEFGH", (12, 18, 20, 18, 7, 10, 24, 20), strict=True):
        ws.column_dimensions[column].width = width
    info = wb.create_sheet("Mode d'emploi")
    for line in [
        "Une ligne par élève. Remplacez les deux lignes d'exemple.",
        "Date de naissance : jj/mm/aaaa. Sexe : F ou M (facultatif).",
        "Téléphone : ancien format (8 chiffres) ou nouveau (01 + 8 chiffres), au choix.",
        "Un parent avec plusieurs enfants : répétez le même numéro, un seul compte sera créé.",
        "Classes existantes cette année : " + (", ".join(classes) or "aucune"),
    ]:
        info.append([line])
    info.column_dimensions["A"].width = 100
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
