from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# Base schema shared by creation and response models
class TaskBase(BaseModel):
    title: str = Field(
        ..., min_length=1, max_length=100, json_schema_extra={"example": "Buy groceries"}
    )
    description: Optional[str] = Field(
        None, json_schema_extra={"example": "Milk, eggs, and bread"}
    )
    completed: bool = Field(default=False)


# Schema expected when creating a new task
class TodoCreate(TaskBase):
    pass


# Schema used for returning task objects back to the client
class TodoResponse(TaskBase):
    # from_attributes lets FastAPI build this straight off a SQLAlchemy Todo.
    model_config = ConfigDict(from_attributes=True)

    id: int
