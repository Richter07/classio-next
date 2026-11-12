"""Formules de moyenne de matière, sur des notes connues d'avance."""

from decimal import Decimal
from types import SimpleNamespace as N

from apps.grades.calculations import Rules, subject_average


def grade(kind, value, max_score=20, weight=1, absent=False):
    return N(value=None if value is None else Decimal(str(value)), is_absent=absent,
             assessment=N(kind=kind, max_score=Decimal(str(max_score)),
                          weight=Decimal(str(weight)), held_on=None, created_at=0))


BENIN = Rules(formula="BENIN")
WEIGHTED = Rules(formula="WEIGHTED")


def test_benin_quiz_average_counts_as_one_mark():
    # Interrogations 10 et 14 → MI = 12 ; devoirs 9 et 15 → (12 + 9 + 15) / 3 = 12
    grades = [grade("QUIZ", 10), grade("QUIZ", 14), grade("HOMEWORK", 9), grade("EXAM", 15)]
    assert subject_average(grades, BENIN) == Decimal(12)
    # La moyenne pondérée, elle, met les quatre notes à égalité : 48 / 4 = 12 aussi ici…
    assert subject_average(grades, WEIGHTED) == Decimal(12)


def test_benin_and_weighted_differ_when_quiz_count_differs():
    grades = [grade("QUIZ", 8), grade("QUIZ", 8), grade("QUIZ", 8), grade("HOMEWORK", 16)]
    assert subject_average(grades, BENIN) == Decimal(12)       # (8 + 16) / 2
    assert subject_average(grades, WEIGHTED) == Decimal(10)    # 40 / 4


def test_marks_are_brought_back_to_the_scale_and_an_absence_counts_zero():
    grades = [grade("QUIZ", 5, max_score=10), grade("HOMEWORK", None, absent=True),
              grade("HOMEWORK", 14)]
    assert subject_average(grades, BENIN) == Decimal(8)        # (10 + 0 + 14) / 3
    assert subject_average(grades, WEIGHTED) == Decimal(8)


def test_subject_detail_and_olympic_ranks():
    from apps.grades.calculations import olympic_ranks, subject_detail

    detail = subject_detail([grade("QUIZ", 8), grade("QUIZ", 12), grade("HOMEWORK", 14),
                             grade("HOMEWORK", None, absent=True)], BENIN)
    assert detail.quiz_average == Decimal(10)
    assert len(detail.homeworks) == 2 and None in detail.homeworks  # « Abs » sur le bulletin
    assert olympic_ranks({"a": 12, "b": 15, "c": 12, "d": 9, "e": None}) == {
        "b": (1, False), "a": (2, True), "c": (2, True), "d": (4, False), "e": (None, False)}


def test_only_quizzes_or_only_homework():
    assert subject_average([grade("QUIZ", 11), grade("QUIZ", 13)], BENIN) == Decimal(12)
    assert subject_average([grade("HOMEWORK", 7)], BENIN) == Decimal(7)
    assert subject_average([], BENIN) is None
