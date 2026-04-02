// =============================================
//  CIPHER MAIL — Main JS
// =============================================

// --- Tab switching (messages page) ---
function switchTab(tab) {
  document.getElementById('pane-recv')?.classList.toggle('hidden', tab !== 'recv');
  document.getElementById('pane-sent')?.classList.toggle('hidden', tab !== 'sent');
  document.getElementById('tab-recv')?.classList.toggle('active', tab === 'recv');
  document.getElementById('tab-sent')?.classList.toggle('active', tab === 'sent');
}

// --- Modal helpers ---
function openModal(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.add('open'); }
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.remove('open'); }
}
// Close modal on overlay click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});
// Close modal on Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
  }
});

// --- Character counter (compose page) ---
const msgArea = document.getElementById('msg-area');
const charCount = document.getElementById('char-count');
if (msgArea && charCount) {
  msgArea.addEventListener('input', () => {
    const len = msgArea.value.length;
    charCount.textContent = `${len} / 2000`;
    charCount.style.color = len > 1800 ? 'var(--rose)' : 'var(--text-3)';
  });
}

// --- Receiver lookup (compose page) ---
let lookupTimer = null;
function lookupUser(val) {
  const statusEl = document.getElementById('receiver-status');
  if (!statusEl) return;
  clearTimeout(lookupTimer);

  const uid = val.trim();
  if (!uid || uid.length < 3) {
    statusEl.innerHTML = '';
    return;
  }

  lookupTimer = setTimeout(async () => {
    try {
      const res = await fetch(`/api/user/${encodeURIComponent(uid)}`);
      if (res.ok) {
        const data = await res.json();
        const name = data.display_name || uid;
        statusEl.innerHTML = `<div class="receiver-preview">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          Found: <strong>${name}</strong>
        </div>`;
      } else {
        statusEl.innerHTML = `<div class="receiver-preview not-found">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          User not found
        </div>`;
      }
    } catch {
      statusEl.innerHTML = '';
    }
  }, 400);
}

// --- Auto-dismiss flash messages after 5s ---
setTimeout(() => {
  document.querySelectorAll('.flash').forEach(f => f.remove());
}, 5000);

// --- Animate page load ---
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.card, .stat-card, .msg-row, .recent-item').forEach((el, i) => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(16px)';
    el.style.transition = `opacity 0.35s ease ${i * 0.05}s, transform 0.35s ease ${i * 0.05}s`;
    requestAnimationFrame(() => {
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    });
  });
});