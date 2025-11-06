from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .models import TaskStatus, TrainingParameters

ProgressCallback = Callable[[float, TaskStatus, Optional[str]], None]


@dataclass
class RunnerConfig:
    task_id: str
    name: str
    dataset_path: str
    output_path: str
    parameters: TrainingParameters
    log_path: Path
    notes: Optional[str]


class BaseRunner:
    def __init__(self, config: RunnerConfig, progress_callback: ProgressCallback):
        self.config = config
        self.progress_callback = progress_callback
        self._thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_wrapper, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._handle_cancel()

    def _handle_cancel(self) -> None:
        """Hook for subclasses to override when a cancel event occurs."""

    def _run_wrapper(self) -> None:
        try:
            self.progress_callback(0.0, TaskStatus.RUNNING, "任务已开始执行")
            self.run()
        except Exception as exc:  # pragma: no cover - defensive programming
            message = f"任务执行失败: {exc}"
            self.progress_callback(0.0, TaskStatus.FAILED, message)
        else:
            if not self._cancel_event.is_set():
                self.progress_callback(1.0, TaskStatus.COMPLETED, "任务已完成")

    def run(self) -> None:
        raise NotImplementedError


class MusubiRunner(BaseRunner):
    """Runner that invokes musubi-tuner through its CLI interface."""

    def __init__(self, config: RunnerConfig, progress_callback: ProgressCallback):
        super().__init__(config, progress_callback)
        self._process: Optional[subprocess.Popen[str]] = None

    def run(self) -> None:  # pragma: no cover - relies on external tool
        executable = shutil.which("musubi-tuner")
        if executable is None:
            raise RuntimeError("未找到 musubi-tuner 可执行文件，请确认已安装并在 PATH 中")

        self._prepare_output_dir()
        command = self._build_command(executable)
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        with open(self.config.log_path, "w", encoding="utf-8") as log_file:
            log_file.write(f"[{datetime.now().isoformat()}] 启动命令: {' '.join(shlex.quote(arg) for arg in command)}\n")
            log_file.flush()
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )

            assert self._process.stdout is not None
            for line in self._process.stdout:
                if self._cancel_event.is_set():
                    break
                log_file.write(line)
                log_file.flush()
                self._parse_progress(line)

            return_code = self._process.wait()
            if return_code != 0 and not self._cancel_event.is_set():
                raise RuntimeError(f"musubi-tuner 训练失败 (退出码 {return_code})")

    def _build_command(self, executable: str) -> list[str]:
        parameters = self.config.parameters
        command = [
            executable,
            "train",
            "--dataset",
            self.config.dataset_path,
            "--output",
            self.config.output_path,
            "--learning-rate",
            str(parameters.learning_rate),
            "--batch-size",
            str(parameters.batch_size),
            "--epochs",
            str(parameters.epochs),
            "--warmup-steps",
            str(parameters.warmup_steps),
            "--gradient-accumulation",
            str(parameters.gradient_accumulation),
            "--lora-rank",
            str(parameters.lora_rank),
            "--lora-alpha",
            str(parameters.lora_alpha),
            "--max-seq-length",
            str(parameters.max_seq_length),
        ]

        config_path = self.config.log_path.with_suffix(".json")
        config_payload = {
            "task_id": self.config.task_id,
            "name": self.config.name,
            "notes": self.config.notes,
            "parameters": json.loads(self.config.parameters.json()),
            "generated_at": datetime.now().isoformat(),
        }
        with open(config_path, "w", encoding="utf-8") as config_file:
            json.dump(config_payload, config_file, ensure_ascii=False, indent=2)

        command.extend(["--config", str(config_path)])
        return command

    def _parse_progress(self, line: str) -> None:
        line_lower = line.lower()
        if "progress" in line_lower:
            value = _extract_percentage(line_lower)
            if value is not None:
                self.progress_callback(value, TaskStatus.RUNNING, "训练进行中")

    def _prepare_output_dir(self) -> None:
        Path(self.config.output_path).mkdir(parents=True, exist_ok=True)

    def _handle_cancel(self) -> None:  # pragma: no cover - requires subprocess
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()


class DummyRunner(BaseRunner):
    """A runner that simulates the training loop for demonstration purposes."""

    def __init__(self, config: RunnerConfig, progress_callback: ProgressCallback, duration: int = 120):
        super().__init__(config, progress_callback)
        self.duration = duration

    def run(self) -> None:
        steps = max(10, int(self.duration / 2))
        self._log(f"开始模拟训练，共 {steps} 步")
        for step in range(steps):
            if self._cancel_event.is_set():
                self._log("检测到取消请求，停止模拟训练")
                self.progress_callback(0.0, TaskStatus.CANCELLED, "任务已取消")
                return

            time.sleep(self.duration / steps)
            progress = (step + 1) / steps
            self._log(f"模拟训练进度: {progress:.2%}")
            self.progress_callback(progress, TaskStatus.RUNNING, "训练进行中")

        self._log("模拟训练完成")

    def _log(self, message: str) -> None:
        timestamp = datetime.now().isoformat()
        with open(self.config.log_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")


def _extract_percentage(line: str) -> Optional[float]:
    import re

    match = re.search(r"(\d{1,3})(?:\.\d+)?\s*%", line)
    if not match:
        return None
    value = float(match.group(1))
    return min(max(value / 100.0, 0.0), 1.0)
