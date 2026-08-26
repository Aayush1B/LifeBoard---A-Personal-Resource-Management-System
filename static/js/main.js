/**
 * LifeBoard - Global UI, Mobile Navigation & AI Voice Controller
 * Academic Project: IGNOU BCA BCSP-064
 * Author: Aayush
 */

let speechRecognizer = null;
let isListening = false;

document.addEventListener('DOMContentLoaded', () => {
  // Mobile Sidebar Drawer & Backdrop Handlers
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  const drawerClose = document.getElementById('mobileDrawerClose');

  function openSidebar() {
    if (sidebar) sidebar.classList.add('open');
    if (backdrop) backdrop.classList.add('active');
  }

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('active');
  }

  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openSidebar();
    });
  }

  if (drawerClose) {
    drawerClose.addEventListener('click', closeSidebar);
  }

  if (backdrop) {
    backdrop.addEventListener('click', closeSidebar);
  }

  // Flash Message Auto Dismiss & Close Buttons (Scoped to Flash Container)
  function dismissAlert(alert) {
    if (!alert || !alert.parentElement) return;
    alert.style.transition = 'all 0.35s ease';
    alert.style.opacity = '0';
    alert.style.transform = 'translateY(-8px)';
    setTimeout(() => {
      if (alert.parentElement) alert.remove();
    }, 350);
  }

  const alertCloseBtns = document.querySelectorAll('.flash-container .alert-close');
  alertCloseBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const alert = btn.closest('.alert');
      if (alert) dismissAlert(alert);
    });
  });

  // Auto-dismiss top temporary flash notifications after 4.5 seconds
  const flashAlerts = document.querySelectorAll('.flash-container .alert');
  flashAlerts.forEach(alert => {
    let dismissTimer = setTimeout(() => {
      dismissAlert(alert);
    }, 4500);

    // Pause timer on hover, resume on mouse leave
    alert.addEventListener('mouseenter', () => clearTimeout(dismissTimer));
    alert.addEventListener('mouseleave', () => {
      dismissTimer = setTimeout(() => dismissAlert(alert), 2500);
    });
  });

  // Modal Open / Close Handlers
  window.openModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.style.display = 'flex';
      document.body.style.overflow = 'hidden';
      const firstInput = modal.querySelector('input, select, textarea');
      if (firstInput) firstInput.focus();
    }
  };

  window.closeModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.style.display = 'none';
      document.body.style.overflow = '';
    }
  };

  // Close modals when clicking backdrop
  document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
      }
    });
  });

  // Keyboard shortcut: ESC to close any open modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay').forEach(modal => {
        if (modal.style.display === 'flex') {
          modal.style.display = 'none';
          document.body.style.overflow = '';
        }
      });
      if (typeof closeVoiceAssistant === 'function') {
        closeVoiceAssistant();
      }
    }
  });

  // Delete Action Confirmations
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('submit', (e) => {
      const msg = el.getAttribute('data-confirm') || 'Are you sure you want to delete this item? This action cannot be undone.';
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });

  // Initialize in-app notification center state
  if (typeof initNotifications === 'function') {
    initNotifications();
  }
});

/* =============================================================
   AI Voice Recognition & Natural Language Logger
   ============================================================= */

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    return null;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  recognition.onstart = function() {
    isListening = true;
    updateVoiceUIState(true, "Listening... Speak naturally now");
  };

  recognition.onresult = function(event) {
    let transcript = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      transcript += event.results[i][0].transcript;
    }
    const input = document.getElementById('voiceTranscriptInput');
    if (input) {
      input.value = transcript;
    }
  };

  recognition.onerror = function(event) {
    isListening = false;
    let msg = "Microphone error. You can type your command below.";
    if (event.error === 'not-allowed') {
      msg = "Microphone permission denied. Please allow microphone access or type below.";
    } else if (event.error === 'no-speech') {
      msg = "No speech detected. Tap the mic to try speaking again.";
    }
    updateVoiceUIState(false, msg);
  };

  recognition.onend = function() {
    isListening = false;
    const input = document.getElementById('voiceTranscriptInput');
    if (input && input.value.trim().length > 0) {
      updateVoiceUIState(false, "Speech captured! Click 'Process & Save' or edit above.");
    } else {
      updateVoiceUIState(false, "Tap microphone icon to start speaking.");
    }
  };

  return recognition;
}

window.startVoiceAssistant = function() {
  openModal('voiceCommandModal');
  const input = document.getElementById('voiceTranscriptInput');
  const resBox = document.getElementById('voiceResultBox');
  if (input) input.value = '';
  if (resBox) { resBox.style.display = 'none'; resBox.innerHTML = ''; }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    updateVoiceUIState(false, "Voice recognition not supported by browser. Type your command below.");
    if (input) input.focus();
    return;
  }

  try {
    if (!speechRecognizer) {
      speechRecognizer = initSpeechRecognition();
    }
    if (speechRecognizer) {
      speechRecognizer.start();
    }
  } catch (err) {
    console.warn("Speech recognition already running or error:", err);
  }
};

window.toggleVoiceRecording = function() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Speech recognition is not supported in this browser. Please type in the text box.");
    return;
  }

  if (!speechRecognizer) {
    speechRecognizer = initSpeechRecognition();
  }

  if (isListening) {
    speechRecognizer.stop();
  } else {
    try {
      speechRecognizer.start();
    } catch (e) {
      console.warn("Restarting recognition:", e);
    }
  }
};

function updateVoiceUIState(listening, statusText) {
  const container = document.getElementById('voiceMicContainer');
  const statusElem = document.getElementById('voiceStatusText');
  const icon = document.getElementById('voiceMicIcon');

  if (container) {
    if (listening) {
      container.classList.add('recording');
    } else {
      container.classList.remove('recording');
    }
  }

  if (statusElem) {
    statusElem.textContent = statusText;
    statusElem.style.color = listening ? '#ef4444' : '#4f46e5';
  }

  if (icon) {
    icon.className = listening ? 'fa-solid fa-microphone-lines' : 'fa-solid fa-microphone';
  }
}

window.closeVoiceAssistant = function() {
  if (speechRecognizer && isListening) {
    speechRecognizer.stop();
  }
  closeModal('voiceCommandModal');
};

window.submitVoiceCommand = function() {
  const input = document.getElementById('voiceTranscriptInput');
  const resBox = document.getElementById('voiceResultBox');
  const submitBtn = document.getElementById('voiceSubmitBtn');

  if (!input || !input.value.trim()) {
    alert("Please speak or type a command first.");
    return;
  }

  const text = input.value.trim();
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
  }

  fetch('/api/voice-command', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    },
    body: JSON.stringify({ speech_text: text })
  })
  .then(res => res.json())
  .then(data => {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Process & Save';
    }

    if (data.success) {
      const info = data.action_info || {};
      if (resBox) {
        resBox.style.display = 'block';
        resBox.innerHTML = `
          <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px;">
            <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: #15803d; margin-bottom: 4px;">
              <i class="fa-solid fa-circle-check"></i>
              <span>Successfully Logged to ${info.module || 'LifeBoard'}!</span>
            </div>
            <div style="font-size: 13.5px; color: #0f172a; margin-bottom: 8px;">
              ${info.action || data.message}
            </div>
            <div style="font-size: 11px; color: #15803d;">Refreshing page in 1.5s...</div>
          </div>
        `;
      }
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } else {
      if (resBox) {
        resBox.style.display = 'block';
        resBox.innerHTML = `
          <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px; color: #991b1b; font-size: 13px;">
            <i class="fa-solid fa-circle-exclamation"></i> ${data.message || 'Could not process command.'}
          </div>
        `;
      }
    }
  })
  .catch(err => {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Process & Save';
    }
    alert("Error processing voice command. Please check your network connection.");
  });
};

/* =============================================================
   Theme Toggle System (Dark & Light Mode)
   ============================================================= */

function initTheme() {
  const saved = localStorage.getItem('lifeboard_theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved ? saved : (prefersDark ? 'dark' : 'light');

  document.documentElement.setAttribute('data-theme', theme);
  updateThemeIcon(theme);
}

function updateThemeIcon(theme) {
  const icons = document.querySelectorAll('.theme-toggle-icon, #themeToggleIcon');
  icons.forEach(icon => {
    if (theme === 'dark') {
      icon.className = 'fa-solid fa-sun theme-toggle-icon';
    } else {
      icon.className = 'fa-solid fa-moon theme-toggle-icon';
    }
  });
}

window.toggleTheme = function() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const target = (current === 'dark') ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', target);
  try {
    localStorage.setItem('lifeboard_theme', target);
  } catch (e) {}
  updateThemeIcon(target);
};

// Initialize Theme immediately and on DOM load
initTheme();
document.addEventListener('DOMContentLoaded', () => {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  updateThemeIcon(current);
});


/* =============================================================
   Command Palette Spotlight (Ctrl + K / Cmd + K)
   ============================================================= */

window.openCommandPalette = function() {
  const overlay = document.getElementById('commandPaletteOverlay');
  const input = document.getElementById('commandPaletteInput');
  if (overlay) {
    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    if (input) {
      input.value = '';
      input.focus();
      filterCommandPalette('');
    }
  }
};

window.closeCommandPalette = function() {
  const overlay = document.getElementById('commandPaletteOverlay');
  if (overlay) {
    overlay.style.display = 'none';
    document.body.style.overflow = '';
  }
};

window.filterCommandPalette = function(query) {
  const q = (query || '').toLowerCase().trim();
  const items = document.querySelectorAll('.cmd-palette-item');
  let hasMatches = false;

  items.forEach(item => {
    const text = item.textContent.toLowerCase();
    const keywords = (item.getAttribute('data-keywords') || '').toLowerCase();
    if (!q || text.includes(q) || keywords.includes(q)) {
      item.style.display = 'flex';
      hasMatches = true;
    } else {
      item.style.display = 'none';
    }
  });

  const noRes = document.getElementById('cmdPaletteNoResults');
  if (noRes) {
    noRes.style.display = hasMatches ? 'none' : 'block';
  }
};

// Global Hotkeys Listener
document.addEventListener('keydown', (e) => {
  // Ctrl + K or Cmd + K -> Command Palette
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    const overlay = document.getElementById('commandPaletteOverlay');
    if (overlay && overlay.style.display === 'flex') {
      closeCommandPalette();
    } else {
      openCommandPalette();
    }
  }

  // Close Command Palette on Escape
  if (e.key === 'Escape') {
    closeCommandPalette();
  }
});


/* =============================================================
   Confetti Milestone Celebration
   ============================================================= */

window.triggerConfetti = function() {
  if (typeof confetti === 'function') {
    confetti({
      particleCount: 80,
      spread: 70,
      origin: { y: 0.6 }
    });
  }
  playSound('taskDone');
};


/* =============================================================
   Pure Web Audio API Sound Effects Engine
   ============================================================= */

let audioCtx = null;

function getAudioContext() {
  if (!audioCtx && (window.AudioContext || window.webkitAudioContext)) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  return audioCtx;
}

window.playSound = function(type) {
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    if (ctx.state === 'suspended') {
      ctx.resume();
    }

    const now = ctx.currentTime;

    if (type === 'taskDone' || type === 'success') {
      [523.25, 659.25, 783.99].forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, now + i * 0.08);
        gain.gain.setValueAtTime(0.1, now + i * 0.08);
        gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.08 + 0.22);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + i * 0.08);
        osc.stop(now + i * 0.08 + 0.22);
      });
    } else if (type === 'expense') {
      [987.77, 1318.51].forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(freq, now + i * 0.06);
        gain.gain.setValueAtTime(0.12, now + i * 0.06);
        gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.06 + 0.18);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + i * 0.06);
        osc.stop(now + i * 0.06 + 0.18);
      });
    } else if (type === 'streak' || type === 'fanfare') {
      [440, 554.37, 659.25, 880].forEach((freq, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(freq, now + i * 0.09);
        gain.gain.setValueAtTime(0.12, now + i * 0.09);
        gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.09 + 0.3);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now + i * 0.09);
        osc.stop(now + i * 0.09 + 0.3);
      });
    }
  } catch (e) {
    console.warn("Web Audio chime disabled/error:", e);
  }
};


/* =============================================================
   Notification Center Dropdown & Interactive Dismiss Controller
   ============================================================= */

function getDismissedNotifs() {
  try {
    return JSON.parse(localStorage.getItem('lifeboard_dismissed_notifs') || '[]');
  } catch (e) {
    return [];
  }
}

function saveDismissedNotif(notifId) {
  if (!notifId) return;
  const dismissed = getDismissedNotifs();
  if (!dismissed.includes(notifId)) {
    dismissed.push(notifId);
    try {
      localStorage.setItem('lifeboard_dismissed_notifs', JSON.stringify(dismissed));
    } catch (e) {}
  }
}

function updateNotificationUI() {
  const container = document.getElementById('notifListContainer');
  if (!container) return;

  const activeItems = container.querySelectorAll('.notification-item:not([style*="display: none"])');
  const count = activeItems.length;

  const bellBadge = document.getElementById('notifBellBadge');
  if (bellBadge) {
    if (count > 0) {
      bellBadge.textContent = count;
      bellBadge.style.display = 'inline-flex';
    } else {
      bellBadge.style.display = 'none';
    }
  }

  const headerCount = document.getElementById('notifHeaderCount');
  if (headerCount) {
    headerCount.textContent = `${count} New`;
    if (count === 0) {
      headerCount.style.display = 'none';
    } else {
      headerCount.style.display = 'inline-flex';
    }
  }

  const emptyState = document.getElementById('notifEmptyState');
  if (emptyState) {
    emptyState.style.display = count === 0 ? 'block' : 'none';
  }
}

window.dismissSingleNotif = function(e, notifId) {
  if (e) {
    e.stopPropagation();
    e.preventDefault();
  }
  const item = document.getElementById(`notif-${notifId}`) || document.querySelector(`[data-notif-id="${notifId}"]`);
  if (item) {
    item.style.transition = 'all 0.25s ease';
    item.style.opacity = '0';
    item.style.transform = 'translateX(24px)';
    item.style.maxHeight = '0px';
    item.style.paddingTop = '0px';
    item.style.paddingBottom = '0px';
    item.style.borderBottom = 'none';
    saveDismissedNotif(notifId);
    setTimeout(() => {
      item.style.display = 'none';
      updateNotificationUI();
    }, 260);
  }
};

window.handleNotifClick = function(e, notifId, link) {
  if (e) e.preventDefault();
  saveDismissedNotif(notifId);
  const item = document.getElementById(`notif-${notifId}`);
  if (item) {
    item.style.transition = 'all 0.2s ease';
    item.style.opacity = '0';
  }
  setTimeout(() => {
    if (link) window.location.href = link;
  }, 150);
};

window.clearAllNotifs = function(e) {
  if (e) e.preventDefault();
  const container = document.getElementById('notifListContainer');
  if (!container) return;

  const items = container.querySelectorAll('.notification-item');
  items.forEach(item => {
    const notifId = item.getAttribute('data-notif-id');
    if (notifId) saveDismissedNotif(notifId);
    item.style.transition = 'all 0.25s ease';
    item.style.opacity = '0';
    item.style.transform = 'translateX(24px)';
  });

  setTimeout(() => {
    items.forEach(item => item.style.display = 'none');
    updateNotificationUI();
  }, 260);
};

window.initNotifications = function() {
  const dismissed = getDismissedNotifs();
  if (dismissed && dismissed.length > 0) {
    dismissed.forEach(id => {
      const el = document.getElementById(`notif-${id}`) || document.querySelector(`[data-notif-id="${id}"]`);
      if (el) el.style.display = 'none';
    });
  }
  updateNotificationUI();
};

window.toggleNotificationDropdown = function() {
  const dd = document.getElementById('notificationDropdown');
  if (dd) {
    dd.classList.toggle('open');
  }
};

// Close dropdown on click outside
document.addEventListener('click', (e) => {
  const dd = document.getElementById('notificationDropdown');
  const btn = document.getElementById('notificationBtn');
  if (dd && btn && !btn.contains(e.target) && !dd.contains(e.target)) {
    dd.classList.remove('open');
  }
});


/* =============================================================
   PWA Service Worker Registration
   ============================================================= */

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => console.log('LifeBoard PWA registered:', reg.scope))
      .catch(err => console.log('PWA registration error:', err));
  });
}


