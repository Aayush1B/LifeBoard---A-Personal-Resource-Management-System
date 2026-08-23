/**
 * LifeBoard - Chart.js Visualizations Controller
 * Academic Project: IGNOU BCA BCSP-064
 * Author: Aayush
 */

// Global Chart.js styling defaults
if (typeof Chart !== 'undefined') {
  Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
  Chart.defaults.color = '#64748b';
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
}

/**
 * Renders the 7-day Workout Activity Bar Chart (FR-09)
 */
function initWorkoutBarChart(canvasId, labels, caloriesData, durationData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Calories Burned (kcal)',
          data: caloriesData,
          backgroundColor: '#4f46e5',
          borderRadius: 6,
          barPercentage: 0.6,
          yAxisID: 'y'
        },
        {
          label: 'Duration (mins)',
          data: durationData,
          backgroundColor: '#38bdf8',
          borderRadius: 6,
          barPercentage: 0.6,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { boxWidth: 12, font: { weight: '600', size: 12 } }
        }
      },
      scales: {
        x: {
          grid: { display: false }
        },
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          beginAtZero: true,
          title: { display: true, text: 'Calories (kcal)' }
        },
        y1: {
          type: 'linear',
          display: true,
          position: 'right',
          beginAtZero: true,
          grid: { drawOnChartArea: false },
          title: { display: true, text: 'Mins' }
        }
      }
    }
  });
}

/**
 * Renders the Monthly Spending Category Doughnut Chart (FR-35)
 */
function initFinancePieChart(canvasId, categories, amounts) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const categoryColors = {
    'Food': '#f59e0b',
    'Transport': '#0ea5e9',
    'Health': '#10b981',
    'Entertainment': '#ec4899',
    'Other': '#8b5cf6',
    'No Expenses Yet': '#e2e8f0'
  };

  const bgColors = categories.map(c => categoryColors[c] || '#6366f1');

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: categories,
      datasets: [{
        data: amounts,
        backgroundColor: bgColors,
        borderWidth: 2,
        borderColor: '#ffffff',
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 12, font: { weight: '600', size: 12 }, padding: 16 }
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const val = context.parsed || 0;
              return ` ₹${val.toLocaleString('en-IN')}`;
            }
          }
        }
      },
      cutout: '68%'
    }
  });
}

/**
 * Renders the 7-day Daily Spending Bar Chart (FR-36)
 */
function initDailySpendingChart(canvasId, labels, amounts) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Daily Spend (₹)',
        data: amounts,
        backgroundColor: '#6366f1',
        borderRadius: 6,
        barPercentage: 0.55
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(context) {
              return ` Spent: ₹${context.parsed.y.toLocaleString('en-IN')}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          beginAtZero: true,
          ticks: {
            callback: function(value) {
              return '₹' + value;
            }
          }
        }
      }
    }
  });
}
