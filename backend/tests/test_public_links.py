from app.public_links import course_slug


def test_course_slug_combines_course_and_term():
    assert course_slug("CS 1428", "Fall 2026") == "cs1428fall2026"


def test_course_slug_removes_punctuation_and_accents():
    assert course_slug("CS-1428: Résumé", "Spring '27") == "cs1428resumespring27"


def test_course_slug_reserves_api_path():
    assert course_slug("API", "") == "courseapi"
