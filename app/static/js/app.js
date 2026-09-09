// Client-side interactions and theme switcher for Personal Notes

(function () {
  "use strict";

  // Initialize Theme (Dark / Light)
  const getStoredTheme = () => localStorage.getItem("theme");
  const setStoredTheme = (theme) => localStorage.setItem("theme", theme);

  const getPreferredTheme = () => {
    const storedTheme = getStoredTheme();
    if (storedTheme) {
      return storedTheme;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };

  const setTheme = (theme) => {
    document.documentElement.setAttribute("data-bs-theme", theme);
    const themeIcon = document.getElementById("theme-icon");
    if (themeIcon) {
      if (theme === "dark") {
        themeIcon.className = "bi bi-moon-stars-fill text-warning";
      } else {
        themeIcon.className = "bi bi-sun-fill text-warning";
      }
    }
  };

  // Helper to add tag to tag input on Create/Edit pages
  window.addTagToInput = function (tagName) {
    const input = document.getElementById("tags");
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

  // Helper to close modals and cleanup backdrops
  const closeModalHandler = () => {
    const modalContainer = document.getElementById("modal-container");
    if (modalContainer) {
      modalContainer.innerHTML = "";
    }
    document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
    document.body.classList.remove("modal-open");
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("padding-right");
  };

  // Apply on immediate load
  setTheme(getPreferredTheme());

  window.addEventListener("DOMContentLoaded", () => {
    setTheme(getPreferredTheme());

    // Theme toggle button click listener
    const themeToggleBtn = document.getElementById("theme-toggle");
    if (themeToggleBtn) {
      themeToggleBtn.addEventListener("click", () => {
        const currentTheme = document.documentElement.getAttribute("data-bs-theme");
        const newTheme = currentTheme === "dark" ? "light" : "dark";
        setStoredTheme(newTheme);
        setTheme(newTheme);
      });
    }

    // Modal close event listener (triggered by HX-Trigger: closeModal)
    document.body.addEventListener("closeModal", closeModalHandler);

    // Escape key listener to dismiss modal
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeModalHandler();
      }
    });

    // Auto-close Bootstrap modals on successful HTMX submissions
    document.body.addEventListener("htmx:afterOnLoad", (event) => {
      if (event.detail.xhr.getResponseHeader("HX-Trigger")?.includes("closeModal")) {
        closeModalHandler();
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
