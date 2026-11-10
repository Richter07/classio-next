from contextlib import contextmanager
from datetime import date

import pytest
from django.db import connection

from apps.academics.models import AcademicYear, Classroom, Level, Period, Subject
from apps.accounts.models import User
from apps.grades.models import Assessment, Grade
from apps.students.models import Student
from apps.tenancy.context import tenant_context
from apps.tenancy.models import School


@contextmanager
def as_app_role():
    """Bascule sur le rôle d'exécution réel : le rôle des tests, lui, contourne le RLS."""
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE classio_app")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")


def build_school(slug: str, phone_suffix: str):
    school = School.objects.create(name=slug, slug=slug, ownership=School.Ownership.PRIVATE)
    with tenant_context(school.pk):
        year = AcademicYear.objects.create(
            label="2026-2027", starts_on=date(2026, 9, 1), ends_on=date(2027, 7, 1)
        )
        level = Level.objects.create(name="6e", rank=1)
        classroom = Classroom.objects.create(year=year, level=level, name="6e A")
        subject = Subject.objects.create(name="Maths")
        period = Period.objects.create(
            year=year, name="T1", rank=1, starts_on=date(2026, 9, 1), ends_on=date(2026, 12, 1)
        )
        student = Student.objects.create(
            matricule=f"M-{phone_suffix}", last_name="Doe", first_name=slug,
            birth_date=date(2014, 1, 1),
        )
        cs = classroom.subjects.create(subject=subject)
        assessment = Assessment.objects.create(
            class_subject=cs, period=period, kind=Assessment.Kind.EXAM
        )
        grade = Grade.objects.create(assessment=assessment, student=student, value=12)
    return {
        "school": school, "year": year, "classroom": classroom, "student": student,
        "assessment": assessment, "grade": grade,
    }


@pytest.fixture
def school_a(db):
    return build_school("ecole-a", "A")


@pytest.fixture
def school_b(db):
    return build_school("ecole-b", "B")


@pytest.fixture
def parent_user(db):
    return User.objects.create_user("+2290197000000")
