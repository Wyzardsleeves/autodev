from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database import Base, engine
from app.models import todo_model  # noqa: F401  -- registers Todo on Base.metadata
from app.routes import todo_routes, view_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Created on startup rather than at import time, so merely importing this
    # module (as the test suite does) never touches the real database file.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Task Manager API",
    description="A foundational FastAPI project layout featuring routers and validation.",
    version="1.0.0",
    lifespan=lifespan,
)

# Include application routers
app.include_router(todo_routes.router)
# Last, so the JSON API always wins a path collision with a page.
app.include_router(view_routes.router)


# "/" now serves the index page, so the machine-readable check moved here.
@app.get("/health", tags=["Root"])
async def read_root():
    return {"status": "healthy", "message": "Welcome to the Task Management API"}

