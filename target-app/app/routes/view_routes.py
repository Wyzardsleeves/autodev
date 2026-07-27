"""HTML pages. Everything here renders a template; JSON lives in todo_routes.

The form pages POST back to themselves and redirect, because a plain <form> can
only speak GET/POST -- the PUT on the JSON API isn't reachable without JS.
Paths avoid the /todos prefix so they never collide with /todos/{todo_id}.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.controllers import todo_controller
from app.database import get_db
from app.schemas.todo_schema import TodoCreate

router = APIRouter(tags=["Views"], include_in_schema=False)

# Resolved off this file rather than the cwd, so `uvicorn` started from anywhere
# still finds the templates.
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "views")


def submitted_todo(
    # Constrained here rather than only inside TodoCreate: a bad field gets a 422
    # from FastAPI instead of a pydantic error escaping as a 500.
    title: str = Form(..., min_length=1, max_length=100),
    description: str | None = Form(None),
    # An unticked checkbox is simply absent from the POST body.
    completed: bool = Form(False),
) -> TodoCreate:
    return TodoCreate(title=title, description=description or None, completed=completed)


def not_found(todo_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Task with ID {todo_id} does not exist",
    )


@router.get("/", response_class=HTMLResponse)
async def todos_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "todo_view.html", {"todos": todo_controller.list_todos(db)}
    )


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse(request, "about.html")


@router.get("/new", response_class=HTMLResponse)
async def new_todo_page(request: Request):
    # No `todo` in the context, so the shared form renders blank.
    return templates.TemplateResponse(request, "newTodo.html", {"action": "/new"})


@router.post("/new")
async def create_todo_from_form(
    payload: TodoCreate = Depends(submitted_todo), db: Session = Depends(get_db)
):
    todo_controller.create_todo(db, payload)
    # 303 so the browser follows with GET and a refresh doesn't re-submit.
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/toggle/{todo_id}")
async def toggle_completed(todo_id: int, db: Session = Depends(get_db)):
    """Flip one todo's completion, driven by the checkboxes on the list page."""
    todo = todo_controller.get_todo(db, todo_id)
    if todo is None:
        raise not_found(todo_id)
    # Rebuilt as a full payload because update_todo overwrites every field.
    todo_controller.update_todo(
        db,
        todo_id,
        TodoCreate(
            title=todo.title,
            description=todo.description,
            completed=not todo.completed,
        ),
    )
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/edit/{todo_id}", response_class=HTMLResponse)
async def update_todo_page(request: Request, todo_id: int, db: Session = Depends(get_db)):
    todo = todo_controller.get_todo(db, todo_id)
    if todo is None:
        raise not_found(todo_id)
    # `todo` in the context is what prefills the shared form.
    return templates.TemplateResponse(
        request, "updateTodo.html", {"action": f"/edit/{todo_id}", "todo": todo}
    )


@router.post("/edit/{todo_id}")
async def update_todo_from_form(
    todo_id: int,
    payload: TodoCreate = Depends(submitted_todo),
    db: Session = Depends(get_db),
):
    if todo_controller.update_todo(db, todo_id, payload) is None:
        raise not_found(todo_id)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
