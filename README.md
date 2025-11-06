# Musubi LoRA 训练控制台

一个基于 FastAPI + 原生前端的轻量级控制台，用于通过 musubi-tuner 创建、管理和监控 LoRA 训练任务。界面支持自定义数据集路径、训练参数、模型产物路径，并提供日志查看及任务取消功能。内置模拟训练器便于在未安装 musubi-tuner 的环境中体验流程。

## 功能概览

- 图形化创建训练任务：配置任务名称、数据集目录、输出目录以及核心训练参数。
- 任务管理：查看任务状态、进度、更新时间并支持一键取消。
- 日志监控：实时轮询训练日志，便于观察训练细节。
- 模拟模式：在无 musubi-tuner 的环境中通过模拟器演示任务生命周期。
- 自动生成配置文件：为每个任务写出 JSON 配置，方便与 musubi-tuner 深度集成。

## 快速开始

### 环境要求

- Python 3.9+
- 已安装 `musubi-tuner`（真实训练场景）
- 或仅需 Python 环境即可体验模拟模式

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器访问 [http://localhost:8000](http://localhost:8000) 即可打开前端界面。

> **提示：** 若环境中未安装 `musubi-tuner`，请勾选界面中的「使用模拟训练」选项体验完整流程。

## 自定义与扩展

- 默认运行目录为 `runs/`，可通过环境变量 `MUSUBI_WORKSPACE` 指定其他路径。
- `backend/task_runner.py` 中的 `MusubiRunner` 负责任务执行，可根据实际的 musubi-tuner CLI 或 Python API 调整命令参数。
- 可结合反向代理或鉴权机制，将该控制台部署到内网团队环境中。

## 项目结构

```
backend/
  main.py          # FastAPI 入口，挂载 API 与前端静态文件
  models.py        # Pydantic 数据模型定义
  task_manager.py  # 任务生命周期管理器
  task_runner.py   # 调用 musubi-tuner 或模拟器的执行器
frontend/
  index.html       # 控制台页面
  styles.css       # 样式
  app.js           # 前端逻辑（使用 Fetch API 与后端交互）
requirements.txt   # Python 依赖
```

## 后续规划建议

- 对接用户认证与权限系统，保障任务安全。
- 支持上传数据集、预览样本、导入/导出配置模板。
- 接入消息通知（如钉钉/企业微信）推送训练完成或失败状态。
