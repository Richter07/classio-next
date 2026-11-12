from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from apps.academics import config_api as config
from apps.accounts import api as auth
from apps.accounts import staff_api as staff
from apps.documents import api as documents
from apps.grades import api as grades
from apps.students import api as students
from apps.students import parent_api as parent


def health(_request):
    return JsonResponse({"status": "ok"})


api = "api/v1/"
urlpatterns = [
    path("admin/", admin.site.urls),
    path(f"{api}health/", health),
    # Connexion
    path(f"{api}auth/csrf/", auth.CsrfView.as_view()),
    path(f"{api}auth/parent/login/", auth.ParentLoginView.as_view()),
    path(f"{api}auth/activate/", auth.ActivateView.as_view()),
    path(f"{api}auth/login/", auth.StaffLoginView.as_view()),
    path(f"{api}auth/password/", auth.PasswordChangeView.as_view()),
    path(f"{api}auth/logout/", auth.LogoutView.as_view()),
    path(f"{api}auth/me/", auth.MeView.as_view()),
    # Parent
    path(f"{api}parent/children/", parent.ChildrenView.as_view()),
    path(f"{api}parent/children/<uuid:school_id>/<uuid:student_id>/",
         parent.ChildDetailView.as_view()),
    path(f"{api}parent/children/<uuid:school_id>/<uuid:student_id>/bulletin.pdf",
         parent.ChildBulletinView.as_view()),
    path(f"{api}parent/notifications/", parent.NotificationsView.as_view()),
    # Enseignant
    path(f"{api}teacher/class-subjects/", grades.TeacherClassSubjectsView.as_view()),
    path(f"{api}teacher/class-subjects/<uuid:pk>/assessments/",
         grades.AssessmentCreateView.as_view()),
    path(f"{api}assessments/<uuid:pk>/", grades.GridView.as_view()),
    path(f"{api}assessments/<uuid:pk>/grades/", grades.GradeBatchView.as_view()),
    path(f"{api}assessments/<uuid:pk>/submit/", grades.SubmitView.as_view()),
    # Direction
    path(f"{api}direction/overview/", grades.DirectionOverviewView.as_view()),
    path(f"{api}direction/assessments/", grades.DirectionAssessmentsView.as_view()),
    path(f"{api}assessments/<uuid:pk>/<str:action>/", grades.AssessmentActionView.as_view()),
    path(f"{api}grades/<uuid:pk>/correct/", grades.GradeCorrectView.as_view()),
    path(f"{api}grades/<uuid:pk>/history/", grades.GradeHistoryView.as_view()),
    path(f"{api}direction/classes/", grades.DirectionClassesView.as_view()),
    path(f"{api}direction/classes/<uuid:pk>/results/", grades.ClassResultsView.as_view()),
    path(f"{api}direction/classes/<uuid:pk>/publish/", grades.ClassPublishView.as_view()),
    path(f"{api}direction/classes/<uuid:pk>/bulletins.pdf", grades.ClassBulletinsView.as_view()),
    path(f"{api}direction/classes/<uuid:pk>/bulletins/", grades.ClassBulletinsJobView.as_view()),
    path(f"{api}direction/classes/<uuid:pk>/release/", grades.ClassReleaseView.as_view()),
    path(f"{api}direction/staff/", staff.StaffListView.as_view()),
    path(f"{api}direction/staff/<uuid:pk>/access-code/", staff.StaffAccessCodeView.as_view()),
    path(f"{api}direction/staff/<uuid:pk>/active/", staff.StaffActiveView.as_view()),
    # Configuration de l'école (direction)
    path(f"{api}config/", config.ConfigSnapshotView.as_view()),
    path(f"{api}config/settings/", config.SettingsView.as_view()),
    path(f"{api}config/periods/preset/", config.PeriodPresetView.as_view()),
    path(f"{api}config/periods/<uuid:pk>/", config.PeriodView.as_view()),
    path(f"{api}config/levels/", config.LevelsView.as_view()),
    path(f"{api}config/levels/<uuid:pk>/", config.LevelView.as_view()),
    path(f"{api}config/levels/<uuid:level_id>/subjects/<uuid:subject_id>/",
         config.LevelSubjectView.as_view()),
    path(f"{api}config/classrooms/", config.ClassroomsView.as_view()),
    path(f"{api}config/classrooms/<uuid:pk>/", config.ClassroomView.as_view()),
    path(f"{api}config/subjects/", config.SubjectsView.as_view()),
    path(f"{api}config/subjects/<uuid:pk>/", config.SubjectView.as_view()),
    path(f"{api}config/class-subjects/<uuid:pk>/", config.ClassSubjectView.as_view()),
    # Documents produits en tâche de fond
    path(f"{api}jobs/<uuid:job_id>/", documents.JobView.as_view()),
    path(f"{api}jobs/<uuid:job_id>/file/", documents.JobFileView.as_view()),
    # Secrétariat
    path(f"{api}office/classrooms/", students.ClassroomsView.as_view()),
    path(f"{api}office/students/", students.StudentsView.as_view()),
    path(f"{api}office/guardians/<uuid:pk>/access-code/",
         students.GuardianAccessCodeView.as_view()),
    path(f"{api}office/access-letters/", students.AccessLettersView.as_view()),
    path(f"{api}office/imports/template.xlsx", students.TemplateView.as_view()),
    path(f"{api}office/imports/", students.ImportCheckView.as_view()),
    path(f"{api}office/imports/<uuid:pk>/apply/", students.ImportApplyView.as_view()),
]
