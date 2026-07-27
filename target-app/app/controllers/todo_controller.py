"""Persistence logic for todos. The only layer that issues queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.todo_model import Todo
from app.schemas.todo_schema import TodoCreate


def list_todos(db: Session, completed: bool | None = None) -> list[Todo]:
    """All todos, optionally narrowed to just completed or just outstanding ones."""
    stmt = select(Todo)
    if completed is not None:
        stmt = stmt.where(Todo.completed == completed)
    return list(db.scalars(stmt.order_by(Todo.id)))


def get_todo(db: Session, todo_id: int) -> Todo | None:
    return db.get(Todo, todo_id)


def create_todo(db: Session, payload: TodoCreate) -> Todo:
    todo = Todo(
        title=payload.title,
        description=payload.description,
        completed=payload.completed,
    )
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


def update_todo(db: Session, todo_id: int, payload: TodoCreate) -> Todo | None:
    """Overwrite an existing todo's fields. Returns None if it doesn't exist."""
    todo = db.get(Todo, todo_id)
    if todo is None:
        return None
    todo.title = payload.title
    todo.description = payload.description
    todo.completed = payload.completed
    db.commit()
    db.refresh(todo)
    return todo


def delete_todo(db: Session, todo_id: int) -> bool:
    """Returns whether a row was actually removed, so the route can 404."""
    todo = db.get(Todo, todo_id)
    if todo is None:
        return False
    db.delete(todo)
    db.commit()
    return True
