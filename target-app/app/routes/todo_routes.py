from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.controllers import todo_controller
from app.database import get_db
from app.schemas.todo_schema import TodoCreate, TodoResponse

router = APIRouter(
    prefix="/todos",
    tags=["To-do's"]
)


@router.get("/", response_model=list[TodoResponse])
async def get_all_tasks(
    completed: bool | None = Query(
        None, description="Filter by completion state; omit to return everything."
    ),
    db: Session = Depends(get_db),
):
    return todo_controller.list_todos(db, completed=completed)


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_single_task(todo_id: int, db: Session = Depends(get_db)):
    todo = todo_controller.get_todo(db, todo_id)
    if todo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {todo_id} does not exist",
        )
    return todo


@router.post("/", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_todo(new_todo: TodoCreate, db: Session = Depends(get_db)):
    return todo_controller.create_todo(db, new_todo)


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(
    todo_id: int, updated: TodoCreate, db: Session = Depends(get_db)
):
    todo = todo_controller.update_todo(db, todo_id, updated)
    if todo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {todo_id} does not exist",
        )
    return todo


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    if not todo_controller.delete_todo(db, todo_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {todo_id} cannot be deleted",
        )
    return None
