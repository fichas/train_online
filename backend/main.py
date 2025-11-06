from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .models import (
    CancelTaskResponse,
    CreateTaskRequest,
    TaskDetail,
    TaskListResponse,
    TaskSummary,
)
from .task_manager import TaskManager

app = FastAPI(title="Musubi LoRA 训练调度平台", version="0.1.0")

workspace = Path(os.getenv("MUSUBI_WORKSPACE", "./runs"))
task_manager = TaskManager(workspace=workspace)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/tasks", response_model=TaskDetail)
def create_task(request: CreateTaskRequest) -> TaskDetail:
    task = task_manager.create_task(request)
    return task


@app.get("/api/tasks", response_model=TaskListResponse)
def list_tasks() -> TaskListResponse:
    tasks = task_manager.list_tasks()
    return TaskListResponse(tasks=tasks)


@app.get("/api/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: str) -> TaskDetail:
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.get("/api/tasks/{task_id}/logs")
def get_task_logs(task_id: str) -> str:
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    log_path = Path(task.log_path)
    if not log_path.exists():
        return ""
    return log_path.read_text(encoding="utf-8")


@app.post("/api/tasks/{task_id}/cancel", response_model=CancelTaskResponse)
def cancel_task(task_id: str) -> CancelTaskResponse:
    response = task_manager.cancel_task(task_id)
    if response is None:
        raise HTTPException(status_code=404, detail="任务不存在或无法取消")
    return response


# Serve the frontend
static_dir = Path(__file__).resolve().parent.parent / "frontend"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
