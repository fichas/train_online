from __future__ import annotations

import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .models import (
    CancelTaskResponse,
    CreateTaskRequest,
    TaskDetail,
    TaskStatus,
    TaskSummary,
    TrainingParameters,
)
from .task_runner import DummyRunner, MusubiRunner, RunnerConfig


class TaskManager:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, TaskDetail] = {}
        self._runners: Dict[str, object] = {}
        self._lock = threading.Lock()

    def list_tasks(self) -> Dict[str, TaskSummary]:
        with self._lock:
            return {task_id: self._to_summary(task) for task_id, task in self._tasks.items()}

    def get_task(self, task_id: str) -> Optional[TaskDetail]:
        with self._lock:
            return self._tasks.get(task_id)

    def create_task(self, request: CreateTaskRequest) -> TaskDetail:
        task_id = uuid.uuid4().hex
        now = datetime.now()
        log_path = self.workspace / f"{task_id}.log"
        task = TaskDetail(
            id=task_id,
            name=request.name,
            dataset_path=request.dataset_path,
            output_path=request.output_path,
            parameters=request.parameters,
            notes=request.notes,
            status=TaskStatus.PENDING,
            progress=0.0,
            created_at=now,
            updated_at=now,
            error_message=None,
            log_path=str(log_path),
        )

        with self._lock:
            self._tasks[task_id] = task

        runner = self._build_runner(task, request.simulate)
        self._runners[task_id] = runner
        runner.start()
        return task

    def cancel_task(self, task_id: str) -> Optional[CancelTaskResponse]:
        runner = self._runners.get(task_id)
        task = self.get_task(task_id)
        if runner is None or task is None:
            return None

        if hasattr(runner, "cancel"):
            runner.cancel()

        self._update_task(task_id, status=TaskStatus.CANCELLED, progress=0.0)
        return CancelTaskResponse(id=task_id, status=TaskStatus.CANCELLED, message="任务已取消")

    def append_log(self, task_id: str, message: str) -> None:
        task = self.get_task(task_id)
        if not task:
            return
        with open(task.log_path, "a", encoding="utf-8") as log_file:
            log_file.write(message + "\n")

    def _build_runner(self, task: TaskDetail, simulate: bool):
        config = RunnerConfig(
            task_id=task.id,
            name=task.name,
            dataset_path=task.dataset_path,
            output_path=task.output_path,
            parameters=TrainingParameters.parse_obj(task.parameters.dict()),
            log_path=Path(task.log_path),
            notes=task.notes,
        )

        runner_cls = DummyRunner if simulate else MusubiRunner
        runner = runner_cls(config, lambda progress, status, message: self._update_task(task.id, progress=progress, status=status, message=message))
        return runner

    def _update_task(
        self,
        task_id: str,
        *,
        progress: Optional[float] = None,
        status: Optional[TaskStatus] = None,
        message: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        with self._lock:
            task = self._tasks[task_id]
            updates = {}
            if progress is not None:
                updates["progress"] = max(0.0, min(progress, 1.0))
            if status is not None:
                updates["status"] = status
                if status == TaskStatus.FAILED and message:
                    updates["error_message"] = message
                elif status in {TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.CANCELLED} and "error_message" not in updates:
                    updates["error_message"] = None
            if error_message is not None:
                updates["error_message"] = error_message
            if updates:
                updates["updated_at"] = datetime.now()
                self._tasks[task_id] = task.copy(update=updates)
                if status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
                    self._runners.pop(task_id, None)

        if message:
            self.append_log(task_id, message)

    def _to_summary(self, task: TaskDetail) -> TaskSummary:
        return TaskSummary(
            id=task.id,
            name=task.name,
            status=task.status,
            progress=task.progress,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
