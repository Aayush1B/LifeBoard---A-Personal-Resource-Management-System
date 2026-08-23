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

  // Flash Message Auto Dismiss & Close Buttons
  const alertCloseBtns = document.querySelectorAll('.alert-close');
  alertCloseBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const alert = btn.closest('.alert');
      if (alert) {
        alert.style.opacity = '0';
        setTimeout(() => alert.remove(), 250);
      }
    });
  });

  // Auto-dismiss success flash alerts after 5 seconds
  const autoDismissAlerts = document.querySelectorAll('.alert-success');
  autoDismissAlerts.forEach(alert => {
    setTimeout(() => {
      if (alert && alert.parentElement) {
        alert.style.transition = 'opacity 0.4s ease';
        alert.style.opacity = '0';
        setTimeout(() => alert.remove(), 400);
      }
    }, 5000);
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
  const icon = document.getElementById('themeToggleIcon');
  if (icon) {
    icon.className = (theme === 'dark') ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
  }
}

window.toggleTheme = function() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const target = (current === 'dark') ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', target);
  localStorage.setItem('lifeboard_theme', target);
  updateThemeIcon(target);
};

// Initialize Theme on load
initTheme();


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
   Notification Center Dropdown Controller
   ============================================================= */

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


