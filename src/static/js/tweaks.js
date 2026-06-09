/* ============================================================================
   SCAManager · Tweaks controller
   Persists theme/variant/density/radius to localStorage.
   ========================================================================== */
(function () {
  "use strict";

  const STATE_KEY = "scamanager.tweaks";
  const DEFAULTS = {
    theme: "dark",
    variant: "refined",
    density: "comfortable",
    radius: "balanced",
    motion: "live",
  };

  function load() {
    try {
      const raw = localStorage.getItem(STATE_KEY);
      if (!raw) return { ...DEFAULTS };
      return { ...DEFAULTS, ...JSON.parse(raw) };
    } catch (e) {
      return { ...DEFAULTS };
    }
  }

  function save(state) {
    try { localStorage.setItem(STATE_KEY, JSON.stringify(state)); } catch (e) {}
  }

  let state = load();

  function apply() {
    const root = document.documentElement;
    root.setAttribute("data-theme", state.theme);
    root.setAttribute("data-variant", state.variant);
    root.setAttribute("data-density", state.density);
    root.setAttribute("data-radius", state.radius);
    root.setAttribute("data-motion", state.motion);

    document.querySelectorAll(".tw-options").forEach((group) => {
      const key = group.dataset.key;
      group.querySelectorAll("button").forEach((b) => {
        b.classList.toggle("is-active", b.dataset.value === state[key]);
      });
    });

    // Update the "current setup" pill in the doc nav
    const pill = document.querySelector("[data-current-setup]");
    if (pill) {
      pill.textContent = `${state.theme} · ${state.variant} · ${state.density.slice(0,4)} · r-${state.radius.slice(0,4)}`;
    }
  }

  function set(key, value) {
    if (!(key in state)) return;
    state[key] = value;
    save(state);
    apply();
  }

  function init() {
    // Wire all tweak option groups
    document.querySelectorAll(".tw-options").forEach((group) => {
      group.addEventListener("click", (e) => {
        const btn = e.target.closest("button");
        if (!btn) return;
        const key = group.dataset.key;
        set(key, btn.dataset.value);
      });
    });

    // Wire collapse handle
    const panel = document.querySelector(".tweaks");
    const head = document.querySelector(".tweaks__head");
    if (panel && head) {
      head.addEventListener("click", () => {
        panel.classList.toggle("is-collapsed");
      });
    }

    // Keyboard shortcut: T toggles tweaks
    // 🔴 remove-before-add 단일 핸들러 — hx-boost body swap 시 document keydown 누적 차단 (#36)
    // Single handler via remove-before-add: prevents document keydown pile-up across hx-boost body swaps.
    if (document._tweaksKeydown) {
      document.removeEventListener("keydown", document._tweaksKeydown);
    }
    document._tweaksKeydown = function (e) {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.key === "t" || e.key === "T") {
        const p = document.querySelector(".tweaks");
        if (p) p.classList.toggle("is-collapsed");
      }
    };
    document.addEventListener("keydown", document._tweaksKeydown);

    apply();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Expose for debugging / external control
  window.SCATweaks = { set, get: () => ({ ...state }) };
})();
