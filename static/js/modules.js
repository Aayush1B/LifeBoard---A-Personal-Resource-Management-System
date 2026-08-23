/**
 * LifeBoard - Module Interactive Operations
 * Academic Project: IGNOU BCA BCSP-064
 * Author: Aayush
 */

// Dynamic BMI Realtime Preview
function updateBmiPreview() {
  const heightInput = document.getElementById('bmiHeight');
  const weightInput = document.getElementById('bmiWeight');
  const previewBox = document.getElementById('bmiPreview');

  if (!heightInput || !weightInput || !previewBox) return;

  const h = parseFloat(heightInput.value);
  const w = parseFloat(weightInput.value);

  if (h > 50 && w > 10) {
    const heightM = h / 100.0;
    const bmi = (w / (heightM * heightM)).toFixed(1);
    let category = "Normal";
    let badgeClass = "badge-success";

    if (bmi < 18.5) {
      category = "Underweight";
      badgeClass = "badge-warning";
    } else if (bmi <= 24.9) {
      category = "Normal (Healthy)";
      badgeClass = "badge-success";
    } else if (bmi <= 29.9) {
      category = "Overweight";
      badgeClass = "badge-warning";
    } else {
      category = "Obese";
      badgeClass = "badge-danger";
    }

    previewBox.innerHTML = `
      <div style="padding: 12px; background: #f8fafc; border-radius: 8px; border: 1px dashed #cbd5e1; text-align: center;">
        <span style="font-size: 13px; color: #64748b;">Computed BMI:</span>
        <strong style="font-size: 20px; color: #0f172a; margin: 0 8px;">${bmi}</strong>
        <span class="badge ${badgeClass}">${category}</span>
      </div>
    `;
  } else {
    previewBox.innerHTML = '';
  }
}

// Edit Task Modal Populator
function openEditTaskModal(taskId, title, description, priority, deadline) {
  const modal = document.getElementById('editTaskModal');
  const form = document.getElementById('editTaskForm');
  if (!modal || !form) return;

  form.action = `/tasks/edit/${taskId}`;
  document.getElementById('editTaskTitle').value = title;
  document.getElementById('editTaskDescription').value = description;
  document.getElementById('editTaskPriority').value = priority;

  // Split deadline if format is "YYYY-MM-DD HH:MM:SS"
  if (deadline) {
    const parts = deadline.split(' ');
    document.getElementById('editTaskDate').value = parts[0] || '';
    if (parts[1]) {
      document.getElementById('editTaskTime').value = parts[1].substring(0, 5);
    }
  }

  openModal('editTaskModal');
}
