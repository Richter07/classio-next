"""Parcours complets par l'API, sous le rôle d'exécution réel (RLS appliqué)."""

import io
import uuid
from decimal import Decimal

import pytest
from django.db import connection
from django.test import Client

from apps.academics.models import Classroom
from apps.grades.models import Assessment, Grade, GradeAudit
from apps.notifications.models import Notification
from apps.students.models import Guardian, Student
from apps.tenancy.context import tenant_context
from apps.tenancy.models import School

pytestmark = pytest.mark.django_db
PASSWORD = "classio-demo-2026"
PARENT = "+2290197000001"
DEMO_CODE = "PARENT26"


@pytest.fixture(autouse=True)
def _world(demo_data, settings):
    from django.core.cache import cache

    settings.DEBUG = False
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE classio_app")


def school(slug):
    return School.objects.get(slug=slug)


def staff(phone, slug="ceg-les-pylones"):
    client = Client(HTTP_HOST="localhost")
    response = client.post("/api/v1/auth/login/",
                           {"phone": phone, "password": PASSWORD, "school": slug},
                           content_type="application/json")
    assert response.status_code == 200, response.content
    return client


def parent(phone=PARENT, password=PASSWORD):
    client = Client(HTTP_HOST="localhost")
    response = client.post("/api/v1/auth/parent/login/", {"phone": phone, "password": password},
                           content_type="application/json")
    assert response.status_code == 200, response.content
    return client


def post(client, url, data=None):
    return client.post(url, data or {}, content_type="application/json")


NEW_PARENT = "+2290197000002"
NEW_PASSWORD = "mangue-ananas-2026"


def activate(client=None, phone=NEW_PARENT, code=DEMO_CODE, password=NEW_PASSWORD, consent=True):
    return post(client or Client(), "/api/v1/auth/activate/",
                {"phone": phone, "code": code, "password": password, "consent": consent})


# ------------------------------------------------------------------ Connexion


class TestParentLogin:
    def test_password_opens_a_30_day_session_with_children_of_both_schools(self):
        client = parent()
        me = client.get("/api/v1/auth/me/").json()
        assert me["is_parent"] and me["roles"] == []
        children = client.get("/api/v1/parent/children/").json()["children"]
        assert {c["school"]["name"] for c in children} == {"CEG Les Pylônes",
                                                           "Collège Saint-Michel"}
        assert client.session.get_expiry_age() >= 60 * 60 * 24 * 29

    def test_old_8_digit_format_is_accepted(self):
        parent(phone="97 00 00 01")

    def test_wrong_password_then_lockout(self):
        for _ in range(5):
            response = post(Client(), "/api/v1/auth/parent/login/",
                            {"phone": PARENT, "password": "mauvais-mot"})
            assert response.status_code == 400
        response = post(Client(), "/api/v1/auth/parent/login/",
                        {"phone": PARENT, "password": PASSWORD})
        assert response.status_code == 429

    def test_staff_without_children_cannot_use_parent_login(self):
        response = post(Client(), "/api/v1/auth/parent/login/",
                        {"phone": "+2290197000012", "password": PASSWORD})
        assert response.status_code == 400

    def test_unknown_number_and_wrong_password_look_the_same(self):
        unknown = post(Client(), "/api/v1/auth/parent/login/",
                       {"phone": "0196111111", "password": "x" * 10}).json()
        wrong = post(Client(), "/api/v1/auth/parent/login/",
                     {"phone": PARENT, "password": "x" * 10}).json()
        assert unknown == wrong

    def test_csrf_is_required_to_log_in(self):
        client = Client(enforce_csrf_checks=True)
        response = post(client, "/api/v1/auth/parent/login/",
                        {"phone": PARENT, "password": PASSWORD})
        assert response.status_code == 403

    def test_password_change(self):
        client = parent()
        assert post(client, "/api/v1/auth/password/",
                    {"current": PASSWORD, "new": "nouveau-mot-2027"}).status_code == 200
        parent(password="nouveau-mot-2027")


class TestActivation:
    def test_first_connection_with_the_code_from_the_school(self):
        client = Client()
        response = activate(client)
        assert response.status_code == 200, response.content
        assert response.json()["kind"] == "parent"
        assert client.get("/api/v1/parent/children/").json()["children"]
        parent(phone=NEW_PARENT, password=NEW_PASSWORD)
        with tenant_context(school("ceg-les-pylones").pk):
            guardian = Guardian.objects.get(phone=NEW_PARENT)
            assert guardian.activated_at and guardian.consent_at and guardian.consent_version

    def test_consent_is_required_and_the_code_survives_a_refusal(self):
        assert activate(consent=False).status_code == 400
        assert activate().status_code == 200

    def test_weak_password_does_not_burn_the_code(self):
        assert activate(password="12345678").status_code == 400
        assert activate().status_code == 200

    def test_code_is_single_use(self):
        assert activate().status_code == 200
        assert activate(password="autre-mot-de-passe").status_code == 400

    def test_code_only_works_with_its_own_number(self):
        assert activate(phone=PARENT).status_code == 400

    def test_dashes_spaces_and_case_are_ignored(self):
        assert activate(code="pare-nt 26").status_code == 200

    def test_attempts_are_limited(self):
        for _ in range(5):
            assert activate(code="AAAABBBB").status_code == 400
        assert activate().status_code == 429

    def test_a_new_code_cancels_the_previous_one(self):
        client = staff("+2290197000011")
        with tenant_context(school("ceg-les-pylones").pk):
            guardian = Guardian.objects.get(phone=NEW_PARENT)
        fresh = post(client, f"/api/v1/office/guardians/{guardian.pk}/access-code/").json()
        assert activate().status_code == 400
        assert activate(code=fresh["code"]).status_code == 200


class TestStaffAccounts:
    def test_director_creates_a_teacher_who_activates_and_logs_in(self):
        director = staff("+2290197000010")
        response = post(director, "/api/v1/direction/staff/",
                        {"full_name": "M. ADANDE Rémi", "phone": "0196123456", "role": "TEACHER"})
        assert response.status_code == 201, response.content
        code = response.json()["access"]["code"]
        result = activate(phone="+2290196123456", code=code, password="tableau-noir-26",
                          consent=False)
        assert result.json() == {"kind": "staff"}
        teacher = Client()
        assert post(teacher, "/api/v1/auth/login/", {"phone": "0196123456",
                    "password": "tableau-noir-26", "school": "ceg-les-pylones"}).status_code == 200

    def test_deactivated_member_cannot_log_in(self):
        director = staff("+2290197000010")
        items = director.get("/api/v1/direction/staff/").json()["items"]
        teacher = next(i for i in items if i["phone"] == "+2290197000014")
        post(director, f"/api/v1/direction/staff/{teacher['id']}/active/", {"is_active": False})
        response = post(Client(), "/api/v1/auth/login/", {
            "phone": "+2290197000014", "password": PASSWORD, "school": "ceg-les-pylones"})
        assert response.status_code == 400

    def test_director_cannot_deactivate_themself(self):
        director = staff("+2290197000010")
        me = next(i for i in director.get("/api/v1/direction/staff/").json()["items"]
                  if i["phone"] == "+2290197000010")
        response = post(director, f"/api/v1/direction/staff/{me['id']}/active/",
                        {"is_active": False})
        assert response.status_code == 400

    def test_only_direction_manages_staff(self):
        assert staff("+2290197000011").get("/api/v1/direction/staff/").status_code == 403


class TestBackgroundDocuments:
    def run_job(self, client, url, body, capture):
        with capture(execute=True):
            response = post(client, url, body)
        assert response.status_code == 202, response.content
        job = response.json()["job"]
        assert client.get(f"/api/v1/jobs/{job}/").json()["status"] == "done"
        return job

    def test_access_letters_for_a_class(self, django_capture_on_commit_callbacks):
        from apps.accounts.models import AccessCode

        client = staff("+2290197000011")
        with tenant_context(school("ceg-les-pylones").pk):
            classroom = Classroom.objects.get(name="6e A")
        before = AccessCode.objects.count()
        job = self.run_job(client, "/api/v1/office/access-letters/",
                           {"classroom": str(classroom.pk)}, django_capture_on_commit_callbacks)
        pdf = client.get(f"/api/v1/jobs/{job}/file/")
        assert pdf.content.startswith(b"%PDF")
        # Un code par parent qui n'a pas encore activé son compte, pas plus.
        assert AccessCode.objects.count() > before
        # Le travail n'appartient qu'à celui qui l'a lancé.
        assert staff("+2290197000010").get(f"/api/v1/jobs/{job}/file/").status_code == 404

    def test_class_bulletins(self, django_capture_on_commit_callbacks):
        client = staff("+2290197000010")
        classes = client.get("/api/v1/direction/classes/").json()["items"]
        job = self.run_job(client, f"/api/v1/direction/classes/{classes[0]['id']}/bulletins/",
                           {}, django_capture_on_commit_callbacks)
        assert client.get(f"/api/v1/jobs/{job}/file/").content.startswith(b"%PDF")


class TestProductionSafeguards:
    def test_real_client_ip_behind_one_proxy(self, settings):
        from django.test import RequestFactory

        from apps.accounts.api import client_ip

        settings.TRUSTED_PROXY_COUNT = 1
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 41.85.1.2",
                                       REMOTE_ADDR="10.0.0.2")
        assert client_ip(request) == "41.85.1.2"
        settings.TRUSTED_PROXY_COUNT = 0
        assert client_ip(request) == "10.0.0.2"

    def test_wildcard_hosts_are_refused_in_production(self):
        import os
        import subprocess
        import sys

        env = {**os.environ, "DJANGO_DEBUG": "False", "ALLOWED_HOSTS": "*",
               "DJANGO_SETTINGS_MODULE": "config.settings"}
        result = subprocess.run([sys.executable, "-c", "import django; django.setup()"],
                                env=env, capture_output=True, text=True)
        assert result.returncode != 0 and "ALLOWED_HOSTS" in result.stderr

    def test_closed_period_blocks_grade_entry(self):
        assessment = draft_assessment()
        with tenant_context(school("ceg-les-pylones").pk):
            assessment.period.is_closed = True
            assessment.period.save(update_fields=["is_closed"])
        client = staff(assessment.class_subject.teacher.user.phone)
        assert not client.get(f"/api/v1/assessments/{assessment.pk}/").json()["can_edit"]
        response = post(client, f"/api/v1/assessments/{assessment.pk}/grades/", {"items": []})
        assert response.status_code == 400

    def test_purge_removes_old_codes(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.accounts.models import AccessCode
        from apps.documents.tasks import purge_expired

        AccessCode.objects.update(expires_at=timezone.now() - timedelta(days=60))
        assert purge_expired()["codes"] >= 1
        assert not AccessCode.objects.exists()


class TestParentSpace:
    def child(self, client, slug):
        return next(c for c in client.get("/api/v1/parent/children/").json()["children"]
                    if c["school"]["name"] == school(slug).name)

    def test_only_published_grades_are_visible(self):
        client = parent()
        child = self.child(client, "ceg-les-pylones")
        body = client.get(f"/api/v1/parent/children/{child['school_id']}/{child['id']}/").json()
        shown = sum(len(s["grades"]) for s in body["subjects"])
        with tenant_context(school("ceg-les-pylones").pk):
            published = Grade.objects.filter(student_id=child["id"], status="PUBLISHED").count()
            pending = Grade.objects.filter(student_id=child["id"]).exclude(
                status="PUBLISHED").count()
        assert shown == published and pending > 0
        # Bulletin pas encore publié par la direction : ni moyenne, ni rang, ni PDF.
        assert body["released"] is False and body["summary"] is None
        assert all(s["average"] is None for s in body["subjects"])

    def test_cannot_open_a_child_that_is_not_theirs(self):
        client = parent()
        child = self.child(client, "ceg-les-pylones")
        with tenant_context(school("ceg-les-pylones").pk):
            other = Student.objects.exclude(pk=child["id"]).exclude(
                guardians__phone=PARENT).first()
        url = f"/api/v1/parent/children/{child['school_id']}/{other.pk}/"
        assert client.get(url).status_code == 404
        assert client.get(f"/api/v1/parent/children/{uuid.uuid4()}/{child['id']}/"
                          ).status_code == 404

    def bulletin(self, client, child):
        base = f"/api/v1/parent/children/{child['school_id']}/{child['id']}/"
        detail = client.get(base).json()
        return detail, client.get(f"{base}bulletin.pdf?period={detail['period']['id']}")

    def test_bulletin_only_once_released_by_the_direction(self):
        client = parent()
        detail, response = self.bulletin(client, self.child(client, "ceg-les-pylones"))
        assert response.status_code == 404 and not detail["has_bulletin"]
        # Saint-Michel a publié les bulletins du trimestre 1 (données de démonstration).
        detail, response = self.bulletin(client, self.child(client, "saint-michel"))
        assert detail["released"] and detail["summary"]["rank"] >= 1
        assert detail["summary"]["class_size"] == 10
        assert all(s["average"] is not None and s["rank_label"] for s in detail["subjects"])
        assert response.status_code == 200 and response.content.startswith(b"%PDF")

    def test_home_shows_the_released_average_only(self):
        children = parent().get("/api/v1/parent/children/").json()["children"]
        by_school = {c["school"]["name"]: c for c in children}
        assert by_school["CEG Les Pylônes"]["average"] is None
        assert by_school["Collège Saint-Michel"]["average"] is not None

    def test_notifications_can_be_marked_read(self):
        client = parent()
        assert client.get("/api/v1/parent/notifications/").json()["unread"] > 0
        post(client, "/api/v1/parent/notifications/")
        assert client.get("/api/v1/parent/notifications/").json()["unread"] == 0

    def test_parent_has_no_staff_access(self):
        client = parent()
        assert client.get("/api/v1/teacher/class-subjects/").status_code == 403
        assert client.get("/api/v1/office/students/").status_code == 403


# ------------------------------------------------------------------ Enseignant


def draft_assessment(slug="ceg-les-pylones"):
    with tenant_context(school(slug).pk):
        return Assessment.objects.filter(grades__status="DRAFT").distinct().select_related(
            "class_subject__teacher__user", "class_subject__classroom").first()


class TestTeacher:
    def test_sees_only_own_classes(self):
        client = staff("+2290197000012")
        items = client.get("/api/v1/teacher/class-subjects/").json()["class_subjects"]
        assert items and {i["teacher"] for i in items} == {"M. DOSSOU Rodrigue"}

    def test_grid_save_is_idempotent_and_detects_conflicts(self):
        assessment = draft_assessment()
        client = staff(assessment.class_subject.teacher.user.phone)
        grid = client.get(f"/api/v1/assessments/{assessment.pk}/").json()
        assert grid["can_edit"]
        empty = next(r for r in grid["rows"] if r["grade_id"] is None)
        mutation = str(uuid.uuid4())
        item = {"student": empty["student_id"], "value": "13,5", "mutation_id": mutation,
                "base_revision": 0}
        url = f"/api/v1/assessments/{assessment.pk}/grades/"
        first = post(client, url, {"items": [item]}).json()["results"][0]
        replay = post(client, url, {"items": [item]}).json()["results"][0]
        assert first["status"] == replay["status"] == "ok"
        assert first["value"] == 13.5 and replay["revision"] == first["revision"]

        stale = {**item, "value": "9", "mutation_id": str(uuid.uuid4()), "base_revision": 0}
        assert post(client, url, {"items": [stale]}).json()["results"][0]["status"] == "conflict"
        too_high = {**item, "value": "25", "mutation_id": str(uuid.uuid4()), "base_revision": 1}
        assert post(client, url, {"items": [too_high]}).json()["results"][0]["status"] == "error"

    def test_cannot_touch_another_teachers_assessment(self):
        assessment = draft_assessment()
        other = "+2290197000014" if assessment.class_subject.teacher.user.phone != \
            "+2290197000014" else "+2290197000013"
        client = staff(other)
        assert client.get(f"/api/v1/assessments/{assessment.pk}/").status_code == 404

    def test_no_new_assessment_in_a_closed_period(self):
        assessment = draft_assessment()
        client = staff(assessment.class_subject.teacher.user.phone)
        with tenant_context(school("ceg-les-pylones").pk):
            from apps.academics.models import Period
            Period.objects.filter(pk=assessment.period_id).update(is_closed=True)
        response = post(client, f"/api/v1/teacher/class-subjects/{assessment.class_subject_id}"
                        "/assessments/", {"period": str(assessment.period_id), "kind": "QUIZ"})
        assert response.status_code == 400

    def test_submit_requires_every_student(self):
        assessment = draft_assessment()
        client = staff(assessment.class_subject.teacher.user.phone)
        url = f"/api/v1/assessments/{assessment.pk}/"
        assert post(client, f"{url}submit/").status_code == 400
        rows = client.get(url).json()["rows"]
        items = [{"student": r["student_id"], "value": "10", "mutation_id": str(uuid.uuid4()),
                  "base_revision": r["revision"]} for r in rows if r["grade_id"] is None]
        post(client, f"{url}grades/", {"items": items})
        assert post(client, f"{url}submit/").json()["submitted"] == len(rows)
        assert not client.get(url).json()["can_edit"]


# ------------------------------------------------------------------ Direction


class TestDirection:
    def test_validate_publish_notifies_parents(self):
        client = staff("+2290197000010")
        pending = client.get("/api/v1/direction/assessments/?state=SUBMITTED").json()["items"]
        assert pending
        target = pending[0]["id"]
        with tenant_context(school("ceg-les-pylones").pk):
            before = Notification.objects.count()
        assert post(client, f"/api/v1/assessments/{target}/validate/").status_code == 200
        assert post(client, f"/api/v1/assessments/{target}/publish/").status_code == 200
        with tenant_context(school("ceg-les-pylones").pk):
            assert Notification.objects.count() > before
            assert not Grade.objects.filter(assessment_id=target).exclude(
                status="PUBLISHED").exists()

    def test_correction_after_publication_is_journaled(self):
        client = staff("+2290197000010")
        with tenant_context(school("ceg-les-pylones").pk):
            grade = Grade.objects.filter(status="PUBLISHED", is_absent=False).first()
        response = post(client, f"/api/v1/grades/{grade.pk}/correct/",
                        {"value": "17", "reason": "Erreur de report"})
        assert response.status_code == 200
        history = client.get(f"/api/v1/grades/{grade.pk}/history/").json()["items"]
        assert history[-1]["reason"] == "Erreur de report"
        assert history[-1]["new_value"] == 17 and history[-1]["by"] == "M. HOUNGBEDJI Pascal"
        with tenant_context(school("ceg-les-pylones").pk):
            assert Notification.objects.filter(kind="CORRECTION").exists()
            assert GradeAudit.objects.filter(grade_id=grade.pk).exists()

    def test_correction_needs_a_reason(self):
        client = staff("+2290197000010")
        with tenant_context(school("ceg-les-pylones").pk):
            grade = Grade.objects.filter(status="PUBLISHED").first()
        assert post(client, f"/api/v1/grades/{grade.pk}/correct/",
                    {"value": "17"}).status_code == 400

    def test_class_results_and_bulletins(self):
        client = staff("+2290197000010")
        classes = client.get("/api/v1/direction/classes/").json()["items"]
        url = f"/api/v1/direction/classes/{classes[0]['id']}/"
        results = client.get(f"{url}results/").json()
        ranks = [s["rank"] for s in results["students"] if s["rank"]]
        assert ranks == sorted(ranks) and ranks[0] == 1
        first = results["students"][0]["id"]
        pdf = client.get(f"{url}bulletins.pdf?student={first}")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        # Toute la classe passe par une tâche de fond (TestBackgroundDocuments).
        assert client.get(f"{url}bulletins.pdf").status_code == 404

    def release_url(self, client, name):
        classes = client.get("/api/v1/direction/classes/").json()["items"]
        target = next(c for c in classes if c["name"] == name)
        return f"/api/v1/direction/classes/{target['id']}/release/"

    def test_release_is_blocked_while_grades_are_not_published(self):
        client = staff("+2290197000010")
        url = self.release_url(client, "6e A")
        state = client.get(url).json()
        assert state["released_at"] is None and state["blockers"]
        response = post(client, url)
        assert response.status_code == 400 and response.json()["blockers"]

    def test_release_freezes_bulletins_and_opens_them_to_parents(self):
        client = staff("+2290197000010")
        url = self.release_url(client, "5e A")
        assert client.get(url).json()["blockers"] == []
        released = post(client, url).json()
        assert released["released"] == 12 and released["released_at"]
        with tenant_context(school("ceg-les-pylones").pk):
            from apps.grades.models import ReportCard
            card = ReportCard.objects.filter(enrollment__classroom__name="5e A").first()
            frozen = card.snapshot
            assert frozen["rows"][0]["quiz"] and len(frozen["rows"][0]["homeworks"]) == 2
            assert Notification.objects.filter(kind="REPORT_CARD").exists()
            grade = Grade.objects.filter(student_id=card.enrollment.student_id,
                                         is_absent=False).first()
        # Une correction après publication ne modifie pas le bulletin remis : la direction
        # est prévenue qu'il faut publier à nouveau.
        post(client, f"/api/v1/grades/{grade.pk}/correct/", {"value": "0", "reason": "Erreur"})
        with tenant_context(school("ceg-les-pylones").pk):
            card.refresh_from_db()
        assert card.snapshot == frozen and client.get(url).json()["outdated"] is True
        # Retrait : le bulletin n'est plus visible des parents.
        assert client.delete(url).json()["released_at"] is None

    def test_teacher_cannot_publish(self):
        client = staff("+2290197000012")
        assessment = draft_assessment()
        assert post(client, f"/api/v1/assessments/{assessment.pk}/publish/").status_code == 403


# ------------------------------------------------------------------ Secrétariat


def workbook(rows):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Matricule", "Nom", "Prénom(s)", "Date de naissance", "Sexe", "Classe",
               "Nom du parent", "Téléphone du parent"])
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    buffer.name = "eleves.xlsx"
    return buffer


class TestImport:
    def test_check_reports_each_line_then_apply_creates_valid_ones(self):
        client = staff("+2290197000011")
        upload = workbook([
            ["N-001", "TOSSOU", "Aimé", "12/03/2014", "M", "6e A", "TOSSOU Jean", "97 11 22 33"],
            ["N-002", "TOSSOU", "Eva", "02/05/2013", "F", "6e B", "TOSSOU Jean", "0197112233"],
            ["N-003", "KAKPO", "Luc", "31/02/2014", "M", "6e A", "KAKPO Paul", "12"],
            ["N-001", "DOUBLON", "X", "01/01/2014", "M", "9e Z", "", "0197000000"],
        ])
        response = client.post("/api/v1/office/imports/", {"file": upload})
        assert response.status_code == 200, response.content.decode()
        report = response.json()
        assert (report["valid"], report["invalid"]) == (2, 2)
        errors = {r["line"]: r["errors"] for r in report["rows"]}
        assert any("Date" in e for e in errors[4]) and any("Téléphone" in e for e in errors[4])
        assert any("double" in e for e in errors[5]) and any("9e Z" in e for e in errors[5])

        result = post(client, f"/api/v1/office/imports/{report['id']}/apply/").json()
        assert (result["students"], result["guardians"]) == (2, 1)
        assert len(result["new_guardian_ids"]) == 1
        assert post(client, f"/api/v1/office/imports/{report['id']}/apply/").status_code == 400
        with tenant_context(school("ceg-les-pylones").pk):
            guardian = Guardian.objects.get(phone="+2290197112233")
            assert guardian.students.count() == 2

    def test_downloaded_template_imports_as_is(self):
        client = staff("+2290197000011")
        template = io.BytesIO(client.get("/api/v1/office/imports/template.xlsx").content)
        template.name = "modele.xlsx"
        report = client.post("/api/v1/office/imports/", {"file": template}).json()
        assert (report["valid"], report["invalid"]) == (2, 0), report

    def test_rejects_unknown_columns(self):
        client = staff("+2290197000011")
        upload = io.BytesIO(b"a;b\n1;2\n")
        upload.name = "x.csv"
        response = client.post("/api/v1/office/imports/", {"file": upload})
        assert response.status_code == 400 and "Colonnes manquantes" in response.json()["detail"]

    def test_manual_student_creation(self):
        client = staff("+2290197000011")
        with tenant_context(school("ceg-les-pylones").pk):
            classroom = Classroom.objects.first()
        response = post(client, "/api/v1/office/students/", {
            "matricule": "M-900", "last_name": "Dah", "first_name": "Inès",
            "birth_date": "2014-06-01", "sex": "F", "classroom": str(classroom.pk),
            "guardian_name": "DAH Martine", "guardian_phone": "0196000001"})
        assert response.status_code == 201 and response.json()["guardian_created"]

    def test_teacher_cannot_import(self):
        client = staff("+2290197000012")
        assert client.get("/api/v1/office/students/").status_code == 403


class TestCalculations:
    def test_weighted_ranks_with_ties_and_absences(self):
        from apps.grades.calculations import compute_class_results

        with tenant_context(school("ceg-les-pylones").pk):
            classroom = Classroom.objects.get(name="6e A")
            assessment = Assessment.objects.filter(
                class_subject__classroom=classroom, grades__status="PUBLISHED").first()
            period = assessment.period
            results = compute_class_results(classroom, period, ["PUBLISHED"])
            ranked = sorted((s for s in results.students if s.rank), key=lambda s: s.rank)
            for a, b in zip(ranked, ranked[1:], strict=False):
                assert a.general >= b.general
            first = ranked[0]
            line = results.subjects[0]
            grades = Grade.objects.filter(
                student_id=first.enrollment.student_id, status="PUBLISHED",
                assessment__class_subject=line.class_subject, assessment__period=period,
                is_absent=False)
            if grades:
                expected = sum(g.value for g in grades) / len(grades)
                assert abs(first.subject_averages[line.class_subject.pk] - expected) \
                    <= Decimal("0.01")
