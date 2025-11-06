from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingParameters(BaseModel):
    learning_rate: float = Field(1e-4, ge=0)
    batch_size: int = Field(1, ge=1)
    epochs: int = Field(1, ge=1)
    warmup_steps: int = Field(0, ge=0)
    gradient_accumulation: int = Field(1, ge=1)
    lora_rank: int = Field(16, ge=1)
    lora_alpha: int = Field(32, ge=1)
    max_seq_length: int = Field(1024, ge=1)


class CreateTaskRequest(BaseModel):
    name: str = Field(..., min_length=1)
    dataset_path: str = Field(..., min_length=1)
    output_path: str = Field(..., min_length=1)
    parameters: TrainingParameters = Field(default_factory=TrainingParameters)
    notes: Optional[str] = None
    simulate: bool = False


class TaskSummary(BaseModel):
    id: str
    name: str
    status: TaskStatus
    progress: float
    created_at: datetime
    updated_at: datetime


class TaskDetail(TaskSummary):
    dataset_path: str
    output_path: str
    parameters: TrainingParameters
    notes: Optional[str]
    error_message: Optional[str]
    log_path: str


class TaskListResponse(BaseModel):
    tasks: Dict[str, TaskSummary]


class UpdateProgress(BaseModel):
    status: TaskStatus
    progress: float
    message: Optional[str] = None
    error_message: Optional[str] = None


class CancelTaskResponse(BaseModel):
    id: str
    status: TaskStatus
    message: Optional[str]
