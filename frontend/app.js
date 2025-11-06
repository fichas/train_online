const API_BASE = window.location.origin.includes('http')
  ? `${window.location.origin}/api`
  : '/api';

const STATUS_LABELS = {
  pending: '待开始',
  running: '进行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

const taskForm = document.querySelector('#task-form');
const tasksContainer = document.querySelector('#tasks');
const taskDetails = document.querySelector('#task-details');
const logsContainer = document.querySelector('#logs');
const cancelButton = document.querySelector('#cancel-button');

let selectedTaskId = null;
let refreshInterval = null;

async function fetchJSON(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || '请求失败');
  }
  if (response.headers.get('content-type')?.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

function renderTasks(tasks) {
  tasksContainer.innerHTML = '';
  const entries = Object.entries(tasks).sort(([, a], [, b]) => new Date(b.updated_at) - new Date(a.updated_at));
  if (!entries.length) {
    tasksContainer.innerHTML = '<p class="empty">暂无任务，快去创建第一个吧！</p>';
    return;
  }

  for (const [id, task] of entries) {
    const item = document.createElement('div');
    item.className = 'task-item';
    item.dataset.taskId = id;
    item.innerHTML = `
      <div class="task-header">
        <h3>${task.name}</h3>
        <span class="status" data-status="${task.status}">${STATUS_LABELS[task.status] ?? task.status}</span>
      </div>
      <div class="progress-bar"><span style="width: ${(task.progress * 100).toFixed(1)}%"></span></div>
      <small>更新时间：${new Date(task.updated_at).toLocaleString()}</small>
    `;
    item.addEventListener('click', () => selectTask(id));
    tasksContainer.appendChild(item);
  }
}

async function refreshTasks() {
  try {
    const data = await fetchJSON(`${API_BASE}/tasks`);
    renderTasks(data.tasks);
  } catch (error) {
    console.error(error);
  }
}

async function selectTask(taskId) {
  selectedTaskId = taskId;
  try {
    const task = await fetchJSON(`${API_BASE}/tasks/${taskId}`);
    updateTaskDetails(task);
    taskDetails.hidden = false;
    await refreshLogs();
    restartLogPolling();
  } catch (error) {
    console.error(error);
  }
}

function updateTaskDetails(task) {
  document.querySelector('#detail-name').textContent = task.name;
  document.querySelector('#detail-status').textContent = STATUS_LABELS[task.status] ?? task.status;
  document.querySelector('#detail-status').dataset.status = task.status;
  document.querySelector('#detail-progress').textContent = `${(task.progress * 100).toFixed(1)}%`;
  document.querySelector('#detail-dataset').textContent = task.dataset_path;
  document.querySelector('#detail-output').textContent = task.output_path;
  document.querySelector('#detail-notes').textContent = task.notes || '—';
  cancelButton.disabled = task.status !== 'running' && task.status !== 'pending';
}

async function refreshLogs() {
  if (!selectedTaskId) return;
  try {
    const logs = await fetchJSON(`${API_BASE}/tasks/${selectedTaskId}/logs`);
    logsContainer.textContent = logs;
    logsContainer.scrollTop = logsContainer.scrollHeight;
  } catch (error) {
    console.error(error);
  }
}

function restartLogPolling() {
  if (refreshInterval) {
    clearInterval(refreshInterval);
  }
  refreshInterval = setInterval(async () => {
    await refreshTasks();
    await refreshLogs();
  }, 3000);
}

taskForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(taskForm);
  const payload = {
    name: formData.get('name'),
    dataset_path: formData.get('dataset_path'),
    output_path: formData.get('output_path'),
    notes: formData.get('notes'),
    simulate: formData.get('simulate') === 'on',
    parameters: {
      learning_rate: Number(formData.get('learning_rate')),
      batch_size: Number(formData.get('batch_size')),
      epochs: Number(formData.get('epochs')),
      warmup_steps: Number(formData.get('warmup_steps')),
      gradient_accumulation: Number(formData.get('gradient_accumulation')),
      lora_rank: Number(formData.get('lora_rank')),
      lora_alpha: Number(formData.get('lora_alpha')),
      max_seq_length: Number(formData.get('max_seq_length')),
    },
  };

  try {
    const task = await fetchJSON(`${API_BASE}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    taskForm.reset();
    document.querySelector('#learning_rate').value = '0.0001';
    document.querySelector('#batch_size').value = '2';
    document.querySelector('#epochs').value = '3';
    document.querySelector('#warmup_steps').value = '100';
    document.querySelector('#gradient_accumulation').value = '1';
    document.querySelector('#lora_rank').value = '16';
    document.querySelector('#lora_alpha').value = '32';
    document.querySelector('#max_seq_length').value = '1024';

    await refreshTasks();
    selectTask(task.id);
  } catch (error) {
    alert(`创建任务失败：${error.message}`);
  }
});

cancelButton.addEventListener('click', async () => {
  if (!selectedTaskId) return;
  if (!confirm('确定要取消该任务吗？')) return;
  try {
    await fetchJSON(`${API_BASE}/tasks/${selectedTaskId}/cancel`, {
      method: 'POST',
    });
    await refreshTasks();
    await selectTask(selectedTaskId);
  } catch (error) {
    alert(`取消任务失败：${error.message}`);
  }
});

refreshTasks();
restartLogPolling();
