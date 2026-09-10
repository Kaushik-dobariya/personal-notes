// Personal Notes - Enhanced Client-side UX, Themes, Toasts & Confirmation

(function () {
  "use strict";

  // ==========================================================================
  // 1. Theme Engine (Light / Dark / Auto-System)
  // ==========================================================================
  const THEME_STORAGE_KEY = "personal-notes-theme";

  const getStoredTheme = () => localStorage.getItem(THEME_STORAGE_KEY) || "auto";
  const setStoredTheme = (theme) => localStorage.setItem(THEME_STORAGE_KEY, theme);

  const getSystemTheme = () =>
    window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";

  const applyTheme = (theme) => {
    const effectiveTheme = theme === "auto" ? getSystemTheme() : theme;
    document.documentElement.setAttribute("data-bs-theme", effectiveTheme);

    const themeIcon = document.getElementById("theme-icon");
    const themeLabel = document.getElementById("theme-current-label");

    if (themeIcon) {
      if (theme === "dark") {
        themeIcon.className = "bi bi-moon-stars-fill text-warning";
      } else if (theme === "light") {
        themeIcon.className = "bi bi-sun-fill text-warning";
      } else {
        themeIcon.className = "bi bi-circle-half text-primary";
      }
    }

    if (themeLabel) {
      themeLabel.textContent = theme.charAt(0).toUpperCase() + theme.slice(1);
    }
  };

  window.setAppTheme = function (theme) {
    setStoredTheme(theme);
    applyTheme(theme);
  };

  // Immediate theme initialization
  applyTheme(getStoredTheme());

  // Listen to OS system color-scheme changes
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      if (getStoredTheme() === "auto") {
        applyTheme("auto");
      }
    });

  // ==========================================================================
  // 2. Toast Notification System
  // ==========================================================================
  window.showToast = function (message, type = "info", title = "") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "toast-container position-fixed bottom-0 end-0 p-3";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = "app-toast";
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "assertive");
    toast.setAttribute("aria-atomic", "true");

    let iconClass = "bi-info-circle-fill";
    let iconTypeClass = "toast-info";
    if (type === "success") {
      iconClass = "bi-check-circle-fill";
      iconTypeClass = "toast-success";
    } else if (type === "warning") {
      iconClass = "bi-exclamation-triangle-fill";
      iconTypeClass = "toast-warning";
    } else if (type === "danger" || type === "error") {
      iconClass = "bi-x-circle-fill";
      iconTypeClass = "toast-danger";
    }

    toast.innerHTML = `
      <div class="toast-icon ${iconTypeClass}">
        <i class="bi ${iconClass}"></i>
      </div>
      <div class="flex-grow-1 small">
        ${title ? `<div class="fw-bold">${title}</div>` : ""}
        <div>${message}</div>
      </div>
      <button type="button" class="btn-close btn-close-sm ms-auto" aria-label="Close" style="font-size: 0.7rem;"></button>
    `;

    const closeBtn = toast.querySelector(".btn-close");
    const removeToast = () => {
      toast.classList.add("toast-hiding");
      setTimeout(() => toast.remove(), 250);
    };

    closeBtn.addEventListener("click", removeToast);
    container.appendChild(toast);

    // Auto-remove after 3.5 seconds
    setTimeout(removeToast, 3500);
  };

  // ==========================================================================
  // 3. Custom Confirmation Modal (Intercepts hx-confirm)
  // ==========================================================================
  let confirmCallback = null;

  window.showConfirmDialog = function (question, onConfirm) {
    const modalEl = document.getElementById("confirm-modal");
    if (!modalEl) {
      if (window.confirm(question)) onConfirm();
      return;
    }

    const msgEl = document.getElementById("confirm-modal-message");
    if (msgEl) msgEl.textContent = question;

    confirmCallback = onConfirm;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  };

  // ==========================================================================
  // 4. Modal and Mobile Drawer Helpers
  // ==========================================================================
  window.closeModal = function () {
    const modalContainer = document.getElementById("modal-container");
    if (modalContainer) {
      modalContainer.innerHTML = "";
    }
    document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
    document.body.classList.remove("modal-open");
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("padding-right");
  };

  window.toggleMobileSidebar = function () {
    const sidebar = document.getElementById("sidebar-menu");
    const backdrop = document.getElementById("sidebar-backdrop");
    if (sidebar) sidebar.classList.toggle("show");
    if (backdrop) backdrop.classList.toggle("show");
  };

  window.closeMobileSidebar = function () {
    const sidebar = document.getElementById("sidebar-menu");
    const backdrop = document.getElementById("sidebar-backdrop");
    if (sidebar) sidebar.classList.remove("show");
    if (backdrop) backdrop.classList.remove("show");
  };

  // Tag helper for forms
  window.addTagToInput = function (tagName) {
    const input = document.getElementById("tag_names") || document.getElementById("tags");
    if (!input) return;
    const current = input.value
      .split(",")
      .map((t) => t.trim().replace(/^#/, ""))
      .filter(Boolean);
    const normalized = tagName.trim().replace(/^#/, "");
    if (!current.includes(normalized)) {
      current.push(normalized);
      input.value = current.join(", ");
    }
  };

  // ==========================================================================
  // 5. Lifecycle Events & HTMX Hooks
  // ==========================================================================
  window.addEventListener("DOMContentLoaded", () => {
    applyTheme(getStoredTheme());

    // Connect confirm button in confirm modal
    const confirmActionBtn = document.getElementById("confirm-modal-action-btn");
    if (confirmActionBtn) {
      confirmActionBtn.addEventListener("click", () => {
        const modalEl = document.getElementById("confirm-modal");
        if (modalEl) {
          const modal = bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
        }
        if (typeof confirmCallback === "function") {
          confirmCallback();
          confirmCallback = null;
        }
      });
    }

    // Intercept HTMX confirm requests
    document.body.addEventListener("htmx:confirm", (evt) => {
      if (evt.target.hasAttribute("hx-confirm")) {
        evt.preventDefault();
        window.showConfirmDialog(evt.detail.question, () => {
          evt.detail.issueRequest(true);
        });
      }
    });

    // Global HTMX loading progress bar
    const progressBar = document.getElementById("htmx-progress-bar");
    document.body.addEventListener("htmx:configRequest", () => {
      if (progressBar) progressBar.classList.add("htmx-loading");
    });
    document.body.addEventListener("htmx:afterOnLoad", () => {
      if (progressBar) progressBar.classList.remove("htmx-loading");
    });
    document.body.addEventListener("htmx:sendError", () => {
      if (progressBar) progressBar.classList.remove("htmx-loading");
      window.showToast("Network error. Please check your connection.", "danger");
    });

    // Listen for server-triggered toasts via HX-Trigger header
    document.body.addEventListener("showToast", (evt) => {
      const d = evt.detail;
      if (typeof d === "string") {
        window.showToast(d, "info");
      } else if (d && d.message) {
        window.showToast(d.message, d.type || "info", d.title || "");
      }
    });

    // Modal close event listener (triggered by HX-Trigger: closeModal)
    document.body.addEventListener("closeModal", window.closeModal);

    // Auto-focus inputs inside swapped elements
    document.body.addEventListener("htmx:afterSwap", (evt) => {
      const input = evt.detail.target.querySelector("input:not([type=hidden]), textarea");
      if (input) {
        input.focus();
        if (input.setSelectionRange && input.value) {
          const len = input.value.length;
          input.setSelectionRange(len, len);
        }
      }
    });

    // Global keyboard shortcuts
    window.addEventListener("keydown", (e) => {
      // Escape: close modal / sidebar
      if (e.key === "Escape") {
        window.closeModal();
        window.closeMobileSidebar();
      }

      // '/' shortcut: focus global search if not already in an input
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes((document.activeElement && document.activeElement.tagName) || "")) {
        e.preventDefault();
        const searchInput = document.getElementById("global-search-input");
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }

      // Ctrl+Enter or Cmd+Enter: submit active form in textarea
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        const activeEl = document.activeElement;
        if (activeEl && activeEl.tagName === "TEXTAREA" && activeEl.form) {
          e.preventDefault();
          const submitBtn = activeEl.form.querySelector("button[type=submit]");
          if (submitBtn) {
            submitBtn.click();
          } else {
            activeEl.form.requestSubmit();
          }
        }
      }
    });

    // Handle authentication redirect from HTMX (401 response)
    document.body.addEventListener("htmx:responseError", (event) => {
      if (event.detail.xhr.status === 401) {
        window.location.href = "/auth/login";
      }
    });

    // Allow HTMX to swap response on 400 and 422 validation errors
    document.body.addEventListener("htmx:beforeSwap", (event) => {
      if (event.detail.xhr.status === 400 || event.detail.xhr.status === 422) {
        event.detail.shouldSwap = true;
        event.detail.isError = false;
      }
    });
  });
})();
