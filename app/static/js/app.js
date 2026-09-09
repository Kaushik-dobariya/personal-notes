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

    // Auto-close Bootstrap modals on successful HTMX submissions
    document.body.addEventListener("htmx:afterOnLoad", (event) => {
      // If the response contains modal-close indicator header
      if (event.detail.xhr.getResponseHeader("HX-Trigger")?.includes("closeModal")) {
        const modalContainer = document.getElementById("modal-container");
        if (modalContainer) {
          modalContainer.innerHTML = "";
        }
        const openModal = document.querySelector(".modal.show");
        if (openModal) {
          const modalInstance = bootstrap.Modal.getInstance(openModal);
          if (modalInstance) {
            modalInstance.hide();
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
