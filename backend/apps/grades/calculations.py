"""Moyennes, coefficients et rangs.

Deux formules de moyenne de matière, au choix de l'école (SchoolSettings.average_formula) :
- BENIN (par défaut) : la moyenne des interrogations compte comme une note, à côté de chaque
  devoir et composition. Ex. (MI + D1 + D2) / 3 ;
- WEIGHTED : moyenne pondérée de toutes les évaluations, chaque note ramenée au barème.
Dans les deux cas :
- une absence compte 0 : aucun élève ne reste sans note à une évaluation (règle des écoles) ;
- moyenne générale = moyenne des matières pondérée par leur coefficient ;
- rang « olympique » : deux élèves à 12,50 sont 3e ex æquo, le suivant est 5e.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal

from apps.academics.models import ClassSubject, LevelSubject, SchoolSettings
from apps.students.models import Enrollment

from .models import Grade

ROUNDING = {"HALF_UP": ROUND_HALF_UP, "DOWN": ROUND_DOWN, "UP": ROUND_UP}


@dataclass
class Rules:
    max_score: Decimal = Decimal("20")
    decimals: int = 2
    rounding: str = "HALF_UP"
    bands: list = field(default_factory=list)
    formula: str = "BENIN"

    def round(self, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return value.quantize(Decimal(1).scaleb(-self.decimals), rounding=ROUNDING[self.rounding])

    def appreciation(self, average: Decimal | None) -> str:
        if average is None:
            return ""
        for band in sorted(self.bands, key=lambda b: Decimal(str(b["min"])), reverse=True):
            if average >= Decimal(str(band["min"])):
                return band["label"]
        return ""


def load_rules() -> Rules:
    settings = SchoolSettings.objects.first()
    if settings is None:
        return Rules()
    return Rules(settings.max_score, settings.decimals, settings.rounding,
                 settings.appreciation_bands, settings.average_formula)


@dataclass
class SubjectLine:
    class_subject: ClassSubject
    coefficient: Decimal
    class_average: Decimal | None = None
    lowest: Decimal | None = None
    highest: Decimal | None = None


@dataclass
class SubjectDetail:
    """Ce qu'affiche une ligne du bulletin : moyenne des interrogations, chaque devoir, chaque
    composition (notes ramenées au barème de l'école ; None = absent)."""

    quiz_average: Decimal | None = None
    homeworks: list = field(default_factory=list)
    exams: list = field(default_factory=list)


@dataclass
class StudentResult:
    enrollment: Enrollment
    subject_averages: dict = field(default_factory=dict)
    subject_details: dict = field(default_factory=dict)
    subject_ranks: dict = field(default_factory=dict)
    general: Decimal | None = None
    rank: int | None = None
    tied: bool = False
    appreciation: str = ""


@dataclass
class ClassResults:
    rules: Rules
    subjects: list
    students: list
    class_average: Decimal | None = None
    highest: Decimal | None = None
    lowest: Decimal | None = None

    def for_student(self, student_id) -> StudentResult | None:
        return next((s for s in self.students if s.enrollment.student_id == student_id), None)

    @property
    def ranked_size(self) -> int:
        return sum(1 for s in self.students if s.general is not None)


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _scaled(grade, rules: Rules) -> Decimal:
    """Note ramenée au barème de l'école. Une absence vaut 0."""
    if grade.is_absent:
        return Decimal(0)
    return grade.value / grade.assessment.max_score * rules.max_score


def _counted(grades):
    return [g for g in grades if g.is_absent or g.value is not None]


def _ordered(grades):
    return sorted(grades, key=lambda g: (g.assessment.held_on is None, g.assessment.held_on,
                                         g.assessment.created_at))


def subject_detail(grades, rules: Rules) -> SubjectDetail:
    marked = _counted(grades)
    quizzes = [_scaled(g, rules) for g in marked if g.assessment.kind == "QUIZ"]
    return SubjectDetail(
        quiz_average=rules.round(sum(quizzes) / len(quizzes)) if quizzes else None,
        # None = absent : le bulletin affiche « Abs », la moyenne compte 0.
        homeworks=[None if g.is_absent else rules.round(_scaled(g, rules))
                   for g in _ordered(marked) if g.assessment.kind == "HOMEWORK"],
        exams=[None if g.is_absent else rules.round(_scaled(g, rules))
               for g in _ordered(marked) if g.assessment.kind == "EXAM"],
    )


def olympic_ranks(values: dict) -> dict:
    """{clé: valeur} -> {clé: (rang, ex æquo)} ; 12,50 et 12,50 sont 3e ex æquo, puis 5e."""
    ordered = sorted((v for v in values.values() if v is not None), reverse=True)
    ranks = {}
    for key, value in values.items():
        if value is None:
            ranks[key] = (None, False)
        else:
            ranks[key] = (ordered.index(value) + 1, ordered.count(value) > 1)
    return ranks


def subject_average(grades, rules: Rules) -> Decimal | None:
    marked = _counted(grades)
    if rules.formula == "BENIN":
        quizzes = [_scaled(g, rules) for g in marked if g.assessment.kind == "QUIZ"]
        others = [_scaled(g, rules) for g in marked if g.assessment.kind != "QUIZ"]
        parts = ([sum(quizzes) / len(quizzes)] if quizzes else []) + others
        return sum(parts) / len(parts) if parts else None
    total = weights = Decimal(0)
    for grade in marked:
        weight = grade.assessment.weight
        total += _scaled(grade, rules) * weight
        weights += weight
    return total / weights if weights else None


def compute_class_results(classroom, period, statuses) -> ClassResults:
    rules = load_rules()
    enrollments = list(
        Enrollment.objects.filter(classroom=classroom)
        .exclude(status=Enrollment.Status.LEFT)
        .select_related("student")
        .order_by("student__last_name", "student__first_name")
    )
    level_coefficients = dict(
        LevelSubject.objects.filter(level_id=classroom.level_id).values_list(
            "subject_id", "coefficient"
        )
    )
    subjects = [
        SubjectLine(cs, cs.coefficient or level_coefficients.get(cs.subject_id) or Decimal(1))
        for cs in ClassSubject.objects.filter(classroom=classroom)
        .select_related("subject", "teacher")
        .order_by("subject__name")
    ]

    by_student = defaultdict(lambda: defaultdict(list))
    grades = Grade.objects.filter(
        assessment__class_subject__classroom=classroom,
        assessment__period=period,
        status__in=statuses,
    ).select_related("assessment")
    for grade in grades:
        by_student[grade.student_id][grade.assessment.class_subject_id].append(grade)

    results = []
    for enrollment in enrollments:
        result = StudentResult(enrollment)
        weighted = coefficients = Decimal(0)
        for line in subjects:
            grades_here = by_student[enrollment.student_id][line.class_subject.pk]
            average = rules.round(subject_average(grades_here, rules))
            result.subject_averages[line.class_subject.pk] = average
            result.subject_details[line.class_subject.pk] = subject_detail(grades_here, rules)
            if average is not None:
                weighted += average * line.coefficient
                coefficients += line.coefficient
        result.general = rules.round(weighted / coefficients) if coefficients else None
        result.appreciation = rules.appreciation(result.general)
        results.append(result)

    ranked = sorted((r for r in results if r.general is not None), key=lambda r: -r.general)
    for index, (rank, tied) in olympic_ranks({i: r.general for i, r in enumerate(results)}).items():
        results[index].rank, results[index].tied = rank, tied

    for line in subjects:
        key = line.class_subject.pk
        for index, rank in olympic_ranks(
                {i: r.subject_averages[key] for i, r in enumerate(results)}).items():
            results[index].subject_ranks[key] = rank
        values = [r.subject_averages[line.class_subject.pk] for r in results]
        values = [v for v in values if v is not None]
        line.class_average = rules.round(_mean(values))
        line.lowest = min(values, default=None)
        line.highest = max(values, default=None)

    generals = [r.general for r in ranked]
    return ClassResults(
        rules=rules,
        subjects=subjects,
        students=results,
        class_average=rules.round(_mean(generals)),
        highest=max(generals, default=None),
        lowest=min(generals, default=None),
    )
