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
function openEditTaskModal(taskId, title, description, priority, deadline, recurring) {
  const modal = document.getElementById('editTaskModal');
  const form = document.getElementById('editTaskForm');
  if (!modal || !form) return;

  form.action = `/tasks/edit/${taskId}`;
  document.getElementById('editTaskTitle').value = title;
  document.getElementById('editTaskDescription').value = description || '';
  document.getElementById('editTaskPriority').value = priority || 'medium';
  
  const recSelect = document.getElementById('editTaskRecurring');
  if (recSelect) {
    recSelect.value = recurring || 'none';
  }

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

// Edit Expense Modal Populator
function openEditExpenseModal(expenseId, amount, category, description, expenseDate) {
  const modal = document.getElementById('editExpenseModal');
  const form = document.getElementById('editExpenseForm');
  if (!modal || !form) return;

  form.action = `/finance/expense/edit/${expenseId}`;
  document.getElementById('editExpenseAmount').value = amount;
  document.getElementById('editExpenseCategory').value = category;
  document.getElementById('editExpenseDescription').value = description || '';
  document.getElementById('editExpenseDate').value = expenseDate || '';

  openModal('editExpenseModal');
}

// -------------------------------------------------------------
// Live Interactive Table & Card Filter / Sort Engine
// -------------------------------------------------------------
function applyLiveFilter(config) {
  const {
    searchInputId,
    filterSelectId,
    filterSelectIds,
    sortSelectId,
    tableBodyId,
    cardListClass,
    itemRowSelector,
    cardSelector,
    onFilter
  } = config;

  const searchInput = document.getElementById(searchInputId);
  const sortSelect = document.getElementById(sortSelectId);
  const tableBody = document.getElementById(tableBodyId);
  const cardList = cardListClass ? document.querySelector(cardListClass) : null;

  const filterSelects = [];
  if (filterSelectId) {
    const el = document.getElementById(filterSelectId);
    if (el) filterSelects.push(el);
  }
  if (Array.isArray(filterSelectIds)) {
    filterSelectIds.forEach(id => {
      const el = document.getElementById(id);
      if (el && !filterSelects.includes(el)) filterSelects.push(el);
    });
  }

  function matchesAllFilters(el) {
    for (const sel of filterSelects) {
      const fVal = sel.value;
      if (fVal === 'all') continue;

      if (sel.id === 'taskPriorityFilter' && el.dataset.priority !== fVal) return false;
      if (sel.id === 'taskRecurrenceFilter' && el.dataset.recurring !== fVal) return false;
      if (sel.id === 'taskUrgencyFilter') {
        if (fVal === 'overdue' && el.dataset.overdue !== '1') return false;
        if (fVal === 'duesoon' && el.dataset.duesoon !== '1') return false;
        if (fVal === 'normal' && (el.dataset.overdue === '1' || el.dataset.duesoon === '1')) return false;
      }
      if (sel.id === 'workoutActivityFilter' && el.dataset.activity !== fVal) return false;
      if (sel.id === 'expenseCategoryFilter' && el.dataset.category !== fVal) return false;
      if (sel.id === 'adminRoleFilter' && el.dataset.role !== fVal) return false;
      if (sel.id === 'adminModuleFilter' && el.dataset.module !== fVal) return false;
    }
    return true;
  }

  function executeFilter() {
    const q = (searchInput ? searchInput.value : '').toLowerCase().trim();
    const sVal = sortSelect ? sortSelect.value : 'default';

    // 1. Process Table Rows
    if (tableBody) {
      const rows = Array.from(tableBody.querySelectorAll(itemRowSelector || 'tr'));
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        const matchesSearch = !q || text.includes(q);
        const passesFilters = matchesAllFilters(row);

        row.style.display = (matchesSearch && passesFilters) ? '' : 'none';
      });

      // Sort rows
      if (sVal !== 'default' && rows.length > 0) {
        rows.sort((a, b) => compareItems(a, b, sVal));
        rows.forEach(r => tableBody.appendChild(r));
      }
    }

    // 2. Process Mobile Cards
    if (cardList) {
      const cards = Array.from(cardList.querySelectorAll(cardSelector || '.mobile-data-card'));
      cards.forEach(card => {
        const text = card.textContent.toLowerCase();
        const matchesSearch = !q || text.includes(q);
        const passesFilters = matchesAllFilters(card);

        card.style.display = (matchesSearch && passesFilters) ? '' : 'none';
      });

      // Sort cards
      if (sVal !== 'default' && cards.length > 0) {
        cards.sort((a, b) => compareItems(a, b, sVal));
        cards.forEach(c => cardList.appendChild(c));
      }
    }

    // 3. Process Kanban Cards
    const kanbanCards = document.querySelectorAll('.kanban-card');
    if (kanbanCards.length > 0) {
      kanbanCards.forEach(card => {
        const text = card.textContent.toLowerCase();
        const matchesSearch = !q || text.includes(q);
        const passesFilters = matchesAllFilters(card);
        card.style.display = (matchesSearch && passesFilters) ? '' : 'none';
      });
    }

    if (onFilter) onFilter();
  }

  function compareItems(a, b, sortRule) {
    if (sortRule === 'created-desc') {
      return (b.dataset.created || '').localeCompare(a.dataset.created || '');
    } else if (sortRule === 'created-asc') {
      return (a.dataset.created || '').localeCompare(b.dataset.created || '');
    } else if (sortRule === 'date-desc') {
      return (b.dataset.date || '').localeCompare(a.dataset.date || '');
    } else if (sortRule === 'date-asc') {
      return (a.dataset.date || '').localeCompare(b.dataset.date || '');
    } else if (sortRule === 'amount-desc') {
      return (parseFloat(b.dataset.amount) || 0) - (parseFloat(a.dataset.amount) || 0);
    } else if (sortRule === 'amount-asc') {
      return (parseFloat(a.dataset.amount) || 0) - (parseFloat(b.dataset.amount) || 0);
    } else if (sortRule === 'title-asc' || sortRule === 'name-asc') {
      const ta = (a.dataset.title || a.dataset.name || '').toLowerCase();
      const tb = (b.dataset.title || b.dataset.name || '').toLowerCase();
      return ta.localeCompare(tb);
    } else if (sortRule === 'title-desc' || sortRule === 'name-desc') {
      const ta = (a.dataset.title || a.dataset.name || '').toLowerCase();
      const tb = (b.dataset.title || b.dataset.name || '').toLowerCase();
      return tb.localeCompare(ta);
    } else if (sortRule === 'priority-desc') {
      const weights = { 'high': 3, 'medium': 2, 'low': 1 };
      return (weights[b.dataset.priority] || 0) - (weights[a.dataset.priority] || 0);
    } else if (sortRule === 'priority-asc') {
      const weights = { 'high': 3, 'medium': 2, 'low': 1 };
      return (weights[a.dataset.priority] || 0) - (weights[b.dataset.priority] || 0);
    } else if (sortRule === 'calories-desc') {
      return (parseFloat(b.dataset.calories) || 0) - (parseFloat(a.dataset.calories) || 0);
    } else if (sortRule === 'duration-desc') {
      return (parseFloat(b.dataset.duration) || 0) - (parseFloat(a.dataset.duration) || 0);
    }
    return 0;
  }

  if (searchInput) searchInput.addEventListener('input', executeFilter);
  filterSelects.forEach(sel => sel.addEventListener('change', executeFilter));
  if (sortSelect) sortSelect.addEventListener('change', executeFilter);
}


