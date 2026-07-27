"""The pages render inside the layout, and the shared form round-trips."""

import pytest


@pytest.mark.parametrize(
    "path,heading",
    [
        ("/", "<h2>Todos</h2>"),
        ("/about", "<h2>About</h2>"),
        ("/new", "<h3>New Todo</h3>"),
    ],
)
def test_page_renders_inside_layout(client, path, heading):
    response = client.get(path)
    assert response.status_code == 200
    body = response.text
    # navbar above the page content, footer below: the layout wrapped the child.
    assert body.index("<nav>") < body.index(heading) < body.index("<footer>")
    assert "<!DOCTYPE html>" in body


def test_list_splits_rows_between_the_two_tables(client):
    client.post("/todos/", json={"title": "Pending one", "description": "d1"})
    client.post("/todos/", json={"title": "Done one", "completed": True})
    body = client.get("/").text

    pending, completed = body.split("Completed:")
    assert "Pending one" in pending and "Done one" not in pending
    assert "Done one" in completed and "Pending one" not in completed
    # Only the completed row's box is ticked.
    assert pending.count("checked") == 0 and completed.count("checked") == 1


def test_empty_list_says_so(client):
    assert client.get("/").text.count("Nothing here.") == 2


def test_checking_the_box_toggles_completion(client):
    client.post("/todos/", json={"title": "Pending one"})

    response = client.post("/toggle/1", follow_redirects=False)
    assert response.status_code == 303
    assert client.get("/todos/1").json()["completed"] is True

    client.post("/toggle/1")
    assert client.get("/todos/1").json()["completed"] is False


def test_toggle_leaves_the_other_fields_alone(client):
    client.post("/todos/", json={"title": "Keep me", "description": "and me"})
    client.post("/toggle/1")
    assert client.get("/todos/1").json() == {
        "id": 1,
        "title": "Keep me",
        "description": "and me",
        "completed": True,
    }


def test_toggling_a_missing_todo_is_404(client):
    assert client.post("/toggle/99").status_code == 404


def test_new_form_is_blank(client):
    body = client.get("/new").text
    assert 'value=""' in body
    assert 'name="completed" checked' not in body


def test_posting_the_new_form_creates_and_redirects(client):
    response = client.post(
        "/new",
        data={"title": "Buy groceries", "description": "Milk", "completed": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert client.get("/todos/").json() == [
        {
            "id": 1,
            "title": "Buy groceries",
            "description": "Milk",
            "completed": True,
        }
    ]


def test_new_form_rejects_empty_title(client):
    assert client.post("/new", data={"title": ""}).status_code == 422


def test_update_form_is_prefilled_with_the_original(client):
    client.post("/todos/", json={"title": "Old", "description": "Was", "completed": True})
    body = client.get("/edit/1").text
    assert 'value="Old"' in body
    assert 'value="Was"' in body
    assert 'name="completed" checked' in body
    assert 'action="/edit/1"' in body


def test_posting_the_update_form_overwrites_and_redirects(client):
    client.post("/todos/", json={"title": "Old", "completed": True})
    # `completed` omitted, the way an unticked checkbox arrives.
    response = client.post(
        "/edit/1", data={"title": "New", "description": ""}, follow_redirects=False
    )
    assert response.status_code == 303
    assert client.get("/todos/1").json() == {
        "id": 1,
        "title": "New",
        "description": None,
        "completed": False,
    }


def test_editing_a_missing_todo_is_404(client):
    assert client.get("/edit/99").status_code == 404
    assert client.post("/edit/99", data={"title": "x"}).status_code == 404
