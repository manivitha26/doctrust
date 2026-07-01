// toast.js – simple toast notification system

const toastContainer = document.createElement('div');
toastContainer.id = 'toastContainer';
toastContainer.style.position = 'fixed';
toastContainer.style.bottom = '1rem';
toastContainer.style.right = '1rem';
toastContainer.style.zIndex = '1000';
document.body.appendChild(toastContainer);

function showToast(message, type = 'info', duration = 3000) {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  toast.style.minWidth = '200px';
  toast.style.marginTop = '0.5rem';
  toast.style.padding = '0.75rem 1rem';
  toast.style.borderRadius = '0.5rem';
  toast.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
  toast.style.background = type === 'error' ? 'rgba(239,68,68,0.9)' : type === 'success' ? 'rgba(34,197,94,0.9)' : 'rgba(59,130,246,0.9)';
  toast.style.color = '#fff';
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, duration);
}

// Export globally (since we are not using modules)
window.showToast = showToast;
