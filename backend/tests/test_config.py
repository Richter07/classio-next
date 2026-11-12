"""Une école neuve, configurée de zéro par sa direction, jusqu'à la première saisie."""

import io

import pytest
from django.core.management import call_command
from django.db import connection
from django.test import Client

from apps.accounts.models import User

pytestmark = pytest.mark.django_db
PASSWORD = "directrice-2026"


@pytest.fixture(autouse=True)
def _env(demo_data, settings):
    from django.core.cache import cache

    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()


@pytest.fixture
def director():
    call_command("create_school", name="École Neuve", slug="ecole-neuve",
                 director_name="Mme NEUVE Awa", director_phone="0196000777", stdout=io.StringIO())
    user = User.objects.get(phone="+2290196000777")
    user.set_password(PASSWORD)
    user.save()
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE classio_app")
    return login("0196000777", PASSWORD, "ecole-neuve")


def login(phone, password, school):
    client = Client()
    response = client.post("/api/v1/auth/login/", {"phone": phone, "password": password,
                                                   "school": school},
                           content_type="application/json")
    assert response.status_code == 200, response.content
    return client


def send(client, method, url, data=None):
    response = getattr(client, method)(f"/api/v1/config/{url}", data or {},
                                       content_type="application/json")
    return response


def test_new_school_is_configured_from_scratch(director):
    config = director.get("/api/v1/config/").json()
    assert config["periods"] == [] and config["classrooms"] == []

    config = send(director, "post", "periods/preset/", {"kind": "TRIMESTER"}).json()
    assert [p["name"] for p in config["periods"]] == ["Trimestre 1", "Trimestre 2", "Trimestre 3"]
    assert send(director, "post", "periods/preset/", {"kind": "SEMESTER"}).status_code == 400

    level = send(director, "post", "levels/", {"name": "6e"}).json()["levels"][0]["id"]
    config = send(director, "post", "subjects/", {"name": "Mathématiques"}).json()
    maths = config["subjects"][0]["id"]
    send(director, "put", f"levels/{level}/subjects/{maths}/", {"coefficient": "3"})

    # Une classe créée après coup reçoit les matières de son niveau.
    config = send(director, "post", "classrooms/", {"name": "6e A", "level": level}).json()
    classroom = config["classrooms"][0]
    assert [s["subject"] for s in classroom["subjects"]] == [maths]

    # Une matière ajoutée au niveau ensuite s'ouvre aussi dans la classe existante.
    french = send(director, "post", "subjects/", {"name": "Français"}).json()
    french = next(s["id"] for s in french["subjects"] if s["name"] == "Français")
    config = send(director, "put", f"levels/{level}/subjects/{french}/",
                  {"coefficient": "2"}).json()
    assert len(config["classrooms"][0]["subjects"]) == 2

    # Un enseignant ajouté par la direction, puis attribué à la classe.
    created = director.post("/api/v1/direction/staff/", {"full_name": "M. PROF Luc",
                            "phone": "0196000778", "role": "TEACHER"},
                            content_type="application/json").json()
    class_subject = config["classrooms"][0]["subjects"][0]["id"]
    config = send(director, "patch", f"class-subjects/{class_subject}/",
                  {"teacher": created["id"], "coefficient": "4"}).json()
    assert config["classrooms"][0]["subjects"][0]["teacher"] == created["id"]

    teacher = User.objects.get(phone="+2290196000778")
    teacher.set_password("tableau-noir-26")
    teacher.save()
    items = login("0196000778", "tableau-noir-26", "ecole-neuve").get(
        "/api/v1/teacher/class-subjects/").json()["class_subjects"]
    assert [(i["classroom"]["name"], len(i["periods"])) for i in items] == [("6e A", 3)]


def test_calculation_rules(director):
    config = send(director, "patch", "settings/", {
        "average_formula": "BENIN", "decimals": 2,
        "appreciation_bands": [{"min": 10, "label": "Passable"}, {"min": 0, "label": "Faible"}],
    }).json()
    assert config["settings"]["average_formula"] == "BENIN"
    assert send(director, "patch", "settings/", {"average_formula": "AUTRE"}).status_code == 400


def test_used_items_cannot_be_deleted(director):
    level = send(director, "post", "levels/", {"name": "6e"}).json()["levels"][0]["id"]
    config = send(director, "post", "classrooms/", {"name": "6e A", "level": level}).json()
    assert send(director, "delete", f"levels/{level}/").status_code == 400
    classroom = config["classrooms"][0]["id"]
    assert send(director, "delete", f"classrooms/{classroom}/").status_code == 200
    assert send(director, "delete", f"levels/{level}/").status_code == 200


def test_duplicates_are_refused(director):
    send(director, "post", "levels/", {"name": "6e"})
    response = send(director, "post", "levels/", {"name": "6e"})
    assert response.status_code == 400 and "existe déjà" in response.json()["detail"]


def test_a_school_only_sees_its_own_configuration(director):
    names = {c["name"] for c in director.get("/api/v1/config/").json()["classrooms"]}
    assert "6e A" not in names  # la 6e A du CEG de démonstration n'apparaît pas
    other = login("+2290197000010", "classio-demo-2026", "ceg-les-pylones")
    level = other.get("/api/v1/config/").json()["levels"][0]["id"]
    assert send(director, "delete", f"levels/{level}/").status_code == 404


def test_only_direction_configures():
    secretary = login("+2290197000011", "classio-demo-2026", "ceg-les-pylones")
    assert secretary.get("/api/v1/config/").status_code == 403
