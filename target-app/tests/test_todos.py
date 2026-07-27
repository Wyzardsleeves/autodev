"""End-to-end tests for the /todos endpoints, against a throwaway database."""


def make_todo(client, title="Buy groceries", completed=False):
    response = client.post(
        "/todos/",
        json={"title": title, "description": "Milk, eggs", "completed": completed},
    )
    assert response.status_code == 201
    return response.json()


def test_health_is_healthy(client):
    assert client.get("/health").json()["status"] == "healthy"


def test_create_assigns_an_id(client):
    todo = make_todo(client)
    assert todo["id"] == 1
    assert todo["title"] == "Buy groceries"
    assert todo["completed"] is False


def test_create_rejects_empty_title(client):
    assert client.post("/todos/", json={"title": ""}).status_code == 422


def test_list_starts_empty_then_returns_created(client):
    assert client.get("/todos/").json() == []
    make_todo(client)
    assert len(client.get("/todos/").json()) == 1


def test_get_single_todo(client):
    todo = make_todo(client)
    assert client.get(f"/todos/{todo['id']}").json()["title"] == "Buy groceries"


def test_get_missing_todo_is_404(client):
    assert client.get("/todos/999").status_code == 404


def test_update_modifies_and_does_not_delete(client):
    """PUT previously deleted the row instead of updating it."""
    todo = make_todo(client)

    response = client.put(
        f"/todos/{todo['id']}",
        json={"title": "Buy oat milk", "description": None, "completed": True},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Buy oat milk"
    assert response.json()["completed"] is True

    # The row must still be there.
    assert client.get(f"/todos/{todo['id']}").status_code == 200
    assert len(client.get("/todos/").json()) == 1


def test_update_missing_todo_is_404(client):
    response = client.put("/todos/999", json={"title": "Nope"})
    assert response.status_code == 404


def test_delete_removes_the_todo(client):
    todo = make_todo(client)
    # Path param and handler arg used to disagree, making this a 422.
    assert client.delete(f"/todos/{todo['id']}").status_code == 204
    assert client.get(f"/todos/{todo['id']}").status_code == 404


def test_delete_missing_todo_is_404(client):
    assert client.delete("/todos/999").status_code == 404


def test_filter_by_completed(client):
    make_todo(client, title="Outstanding", completed=False)
    make_todo(client, title="Finished", completed=True)

    outstanding = client.get("/todos/?completed=false").json()
    assert [t["title"] for t in outstanding] == ["Outstanding"]

    finished = client.get("/todos/?completed=true").json()
    assert [t["title"] for t in finished] == ["Finished"]

    assert len(client.get("/todos/").json()) == 2


def test_todos_are_isolated_between_tests(client):
    """Guards the fixture itself: leakage here would make the agent's gate flaky."""
    assert client.get("/todos/").json() == []
