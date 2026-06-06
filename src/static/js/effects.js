/* ============================================================================
   SCAManager · Effects controller
   ----------------------------------------------------------------------------
   - Stagger entry animations via IntersectionObserver
   - Count-up animation for KPI numbers
   - Score-bar / frequency-bar grow-in
   - SVG chart line draw + donut segment grow
   - Tabs sliding indicator
   - Nav active pill slide
   - Smooth in-page scroll
   All effects respect [data-motion="still"] and prefers-reduced-motion.
   ========================================================================== */
(function () {
  "use strict";

  const reduced = () =>
    document.documentElement.getAttribute("data-motion") === "still" ||
    matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  /* ----- shared IntersectionObserver factory ------------------------------ */
  function onceInView(elements, callback, opts = { threshold: 0.15, rootMargin: "0px 0px -60px 0px" }) {
    if (!("IntersectionObserver" in window)) {
      elements.forEach((el) => callback(el));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          callback(e.target);
          io.unobserve(e.target);
        }
      });
    }, opts);
    elements.forEach((el) => io.observe(el));
  }

  /* ----- 1. Entry animations (stagger via --idx) -------------------------- */
  function setupEntryAnimations() {
    document.body.classList.add("fx-ready");

    const groups = [
      ".kpi-row",
      ".tk-grid",
      ".tk-grid--3",
      ".tk-grid--4",
      ".tk-grid--5",
      ".repo-grid",
      ".breakdown",
      ".freq-list",
      ".reason-list",
      ".detail-grid",
      ".dash-grid",
    ];
    groups.forEach((sel) => {
      document.querySelectorAll(sel).forEach((container) => {
        Array.from(container.children).forEach((child, idx) => {
          child.style.setProperty("--idx", idx);
        });
      });
    });

    const targets = document.querySelectorAll(
      ".fx, .kpi, .principle, .full-card, .repo-card, .demo-grid, .detail-hero, .swatch, .tk-card, .freq-row, .reason-row, .breakdown__row, .issue, .pager, .alert, .section__head, .frame"
    );
    targets.forEach((el) => el.classList.add("fx-enter"));

    if (reduced()) {
      targets.forEach((el) => el.classList.add("is-in-view"));
      return;
    }

    onceInView(Array.from(targets), (el) => {
      el.classList.add("is-in-view");
    });
  }

  /* ----- 2. Count-up animation ------------------------------------------- */
  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

  function animateNumber(textNode, target, duration = 1100, suffix = "") {
    if (reduced()) {
      textNode.nodeValue = formatNumber(target) + suffix;
      return;
    }
    const start = performance.now();
    const initial = 0;

    function step(now) {
      const t = Math.min((now - start) / duration, 1);
      const eased = easeOutCubic(t);
      const v = initial + (target - initial) * eased;
      textNode.nodeValue = formatNumber(v) + suffix;
      if (t < 1) requestAnimationFrame(step);
      else textNode.nodeValue = formatNumber(target) + suffix;
    }
    requestAnimationFrame(step);
  }

  function formatNumber(v) {
    const isFloat = Math.abs(v - Math.round(v)) > 0.01;
    if (isFloat) return v.toFixed(1);
    return Math.round(v).toLocaleString();
  }

  function setupCountUp() {
    // Match: leading number in elements with count-up role
    const candidates = document.querySelectorAll(".kpi__value, .repo-card__score, .detail-hero__num, .reason-row__count, .freq-row__count, .breakdown__val");
    const targets = [];
    candidates.forEach((el) => {
      // Find first text node with numeric content
      for (const node of el.childNodes) {
        if (node.nodeType === 3) {
          const txt = node.nodeValue.trim();
          const m = txt.match(/-?\d+(?:\.\d+)?/);
          if (m) {
            const target = parseFloat(m[0]);
            const suffix = txt.slice(m.index + m[0].length); // anything after number (e.g., %)
            targets.push({ node, target, suffix, host: el });
            // pre-fill 0 so the initial paint isn't the final number
            node.nodeValue = "0" + suffix;
            break;
          }
        }
      }
    });
    onceInView(targets.map((t) => t.host), (host) => {
      const t = targets.find((x) => x.host === host);
      if (t) animateNumber(t.node, t.target, 1100, t.suffix);
    });
  }

  /* ----- 3. Score-bar grow-in -------------------------------------------- */
  function setupScoreBars() {
    document.querySelectorAll(".score-bar").forEach((bar) => {
      const inline = bar.style.getPropertyValue("--sb-pct").trim();
      if (!inline) return;
      bar.dataset.sbPct = inline;
      bar.style.setProperty("--sb-pct", "0%");
    });
    const bars = Array.from(document.querySelectorAll(".score-bar[data-sb-pct]"));
    if (reduced()) {
      bars.forEach((b) => b.style.setProperty("--sb-pct", b.dataset.sbPct));
      return;
    }
    onceInView(bars, (b) => {
      // small stagger
      const delay = 80 + Math.random() * 120;
      setTimeout(() => b.style.setProperty("--sb-pct", b.dataset.sbPct), delay);
    });
  }

  /* ----- 4. Frequent issue bars ------------------------------------------ */
  function setupFreqBars() {
    document.querySelectorAll(".freq-row__bar-fill").forEach((fill) => {
      const target = fill.style.width;
      fill.dataset.targetWidth = target || "100%";
      fill.style.width = "0%";
    });
    const fills = Array.from(document.querySelectorAll(".freq-row__bar-fill[data-target-width]"));
    if (reduced()) {
      fills.forEach((f) => (f.style.width = f.dataset.targetWidth));
      return;
    }
    onceInView(fills.map((f) => f.closest(".freq-row")), (row) => {
      const f = row.querySelector(".freq-row__bar-fill");
      if (f) {
        const delay = (parseInt(row.style.getPropertyValue("--idx")) || 0) * 80;
        setTimeout(() => (f.style.width = f.dataset.targetWidth), delay);
      }
    });
  }

  /* ----- 5. SVG chart line draw-in --------------------------------------- */
  function setupChartLines() {
    document.querySelectorAll("svg path[d]").forEach((path) => {
      // Only animate stroked lines, not filled areas
      const stroke = path.getAttribute("stroke");
      if (!stroke || stroke === "none") return;
      const fill = path.getAttribute("fill");
      if (fill && fill !== "none" && !fill.startsWith("url")) return;
      // Skip paths that already have a dasharray pattern (like dashed reference lines)
      if (path.getAttribute("stroke-dasharray")) return;
      try {
        const len = path.getTotalLength();
        if (len < 4) return;
        path.dataset.len = len;
        path.style.strokeDasharray = `${len}`;
        path.style.strokeDashoffset = `${len}`;
      } catch (e) {}
    });
    const paths = Array.from(document.querySelectorAll("svg path[data-len]"));
    if (reduced()) {
      paths.forEach((p) => (p.style.strokeDashoffset = "0"));
      return;
    }
    onceInView(
      paths.map((p) => p.closest("svg")).filter(Boolean),
      (svg) => {
        svg.querySelectorAll("path[data-len]").forEach((p, idx) => {
          p.style.transition = "stroke-dashoffset 1500ms cubic-bezier(0.16, 1, 0.3, 1)";
          p.style.transitionDelay = `${idx * 100}ms`;
          // Use rAF to ensure transition kicks in
          requestAnimationFrame(() => {
            p.style.strokeDashoffset = "0";
          });
        });
        // also fade-in circles (data points)
        svg.querySelectorAll("circle").forEach((c, idx) => {
          c.style.opacity = "0";
          c.style.transform = "scale(0.4)";
          c.style.transformOrigin = "center";
          c.style.transformBox = "fill-box";
          c.style.transition = "opacity 400ms ease-out, transform 400ms cubic-bezier(0.34, 1.56, 0.64, 1)";
          setTimeout(() => {
            c.style.opacity = "1";
            c.style.transform = "scale(1)";
          }, 600 + idx * 80);
        });
      }
    );
  }

  /* ----- 6. SVG donut segments grow -------------------------------------- */
  function setupChartDonuts() {
    document.querySelectorAll("svg").forEach((svg) => {
      const segments = svg.querySelectorAll("circle[stroke-dasharray]");
      if (segments.length < 2) return;
      segments.forEach((seg) => {
        const orig = seg.getAttribute("stroke-dasharray");
        if (!orig) return;
        seg.dataset.dasharray = orig;
        seg.setAttribute("stroke-dasharray", "0 9999");
      });
    });
    const donutSvgs = Array.from(document.querySelectorAll("svg")).filter((s) =>
      s.querySelector("circle[data-dasharray]")
    );
    if (reduced()) {
      donutSvgs.forEach((svg) =>
        svg.querySelectorAll("circle[data-dasharray]").forEach((seg) => {
          seg.setAttribute("stroke-dasharray", seg.dataset.dasharray);
        })
      );
      return;
    }
    onceInView(donutSvgs, (svg) => {
      svg.querySelectorAll("circle[data-dasharray]").forEach((seg, idx) => {
        seg.style.transition = "stroke-dasharray 900ms cubic-bezier(0.16, 1, 0.3, 1)";
        seg.style.transitionDelay = `${200 + idx * 120}ms`;
        requestAnimationFrame(() => seg.setAttribute("stroke-dasharray", seg.dataset.dasharray));
      });
    });
  }

  /* ----- 7. Tabs sliding indicator --------------------------------------- */
  // 모든 탭 인디케이터를 활성 탭 위치로 재배치 (resize 단일 전역 핸들러용)
  // Reposition every tab indicator onto its active tab (used by the single resize handler).
  function repositionAllTabIndicators() {
    document.querySelectorAll(".tabs").forEach((group) => {
      const ind = group.querySelector(".tabs__indicator");
      const active = group.querySelector(".tabs__tab.is-active");
      if (!ind || !active) return;
      const groupRect = group.getBoundingClientRect();
      const r = active.getBoundingClientRect();
      ind.style.transition = "none";
      ind.style.width = `${r.width}px`;
      ind.style.transform = `translateX(${r.left - groupRect.left}px)`;
    });
  }

  function setupTabs() {
    document.querySelectorAll(".tabs").forEach((group) => {
      let ind = group.querySelector(".tabs__indicator");
      if (!ind) {
        ind = document.createElement("span");
        ind.className = "tabs__indicator";
        group.prepend(ind);
      }
      function position(tab, animated = true) {
        if (!tab) return;
        const groupRect = group.getBoundingClientRect();
        const r = tab.getBoundingClientRect();
        ind.style.transition = animated
          ? "transform var(--dur-base) var(--ease-spring), width var(--dur-base) var(--ease-spring)"
          : "none";
        ind.style.width = `${r.width}px`;
        ind.style.transform = `translateX(${r.left - groupRect.left}px)`;
      }
      const active = group.querySelector(".tabs__tab.is-active");
      position(active, false);
      group.querySelectorAll(".tabs__tab").forEach((t) => {
        t.addEventListener("click", () => {
          group.querySelectorAll(".tabs__tab").forEach((x) => x.classList.remove("is-active"));
          t.classList.add("is-active");
          position(t);
        });
      });
    });

    // re-measure on layout shift — remove-before-add 단일 전역 핸들러 (hx-boost 재방문 시 누적 차단)
    // Single global resize handler via remove-before-add: prevents listener pile-up across hx-boost re-navigations.
    if (document._tabsResizeHandler) {
      window.removeEventListener("resize", document._tabsResizeHandler);
    }
    document._tabsResizeHandler = repositionAllTabIndicators;
    window.addEventListener("resize", document._tabsResizeHandler);
  }

  /* ----- 8. Nav sliding active indicator --------------------------------- */
  function setupNavMagnet() {
    document.querySelectorAll(".nav__links").forEach((group) => {
      let ind = group.querySelector(".nav__indicator");
      if (!ind) {
        ind = document.createElement("span");
        ind.className = "nav__indicator";
        group.appendChild(ind);
      }
      function position(link, animated = true) {
        if (!link) return;
        const groupRect = group.getBoundingClientRect();
        const r = link.getBoundingClientRect();
        ind.style.transition = animated
          ? "transform var(--dur-base) var(--ease-spring), width var(--dur-base) var(--ease-spring), opacity var(--dur-base) ease"
          : "none";
        ind.style.width = `${r.width}px`;
        ind.style.transform = `translateX(${r.left - groupRect.left}px)`;
        ind.style.opacity = "1";
      }
      const active = group.querySelector(".nav__link.is-active");
      position(active, false);
      group.querySelectorAll(".nav__link").forEach((l) => {
        l.addEventListener("click", (e) => {
          e.preventDefault();
          group.querySelectorAll(".nav__link").forEach((x) => x.classList.remove("is-active"));
          l.classList.add("is-active");
          position(l);
        });
      });
    });
  }

  /* ----- 9. Smooth scroll for in-page anchors ---------------------------- */
  function setupSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach((a) => {
      a.addEventListener("click", (e) => {
        const id = a.getAttribute("href").slice(1);
        if (!id) return;
        const target = document.getElementById(id);
        if (!target) return;
        e.preventDefault();
        const offset = 80;
        const y = target.getBoundingClientRect().top + window.scrollY - offset;
        window.scrollTo({ top: y, behavior: reduced() ? "auto" : "smooth" });
      });
    });
  }

  /* ----- 10. Subtle magnetic hover on cards ----------------------------- */
  function setupMagnetic() {
    if (reduced()) return;
    const targets = document.querySelectorAll(".kpi, .repo-card, .principle");
    targets.forEach((el) => {
      let raf = null;
      el.addEventListener("mousemove", (e) => {
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(() => {
          const r = el.getBoundingClientRect();
          const x = (e.clientX - r.left) / r.width - 0.5;
          const y = (e.clientY - r.top) / r.height - 0.5;
          el.style.setProperty("--mx", `${x * 100}%`);
          el.style.setProperty("--my", `${y * 100}%`);
          el.style.setProperty("--tilt-x", `${-y * 1.5}deg`);
          el.style.setProperty("--tilt-y", `${x * 1.5}deg`);
        });
      });
      el.addEventListener("mouseleave", () => {
        el.style.setProperty("--tilt-x", "0deg");
        el.style.setProperty("--tilt-y", "0deg");
      });
    });
  }

  function init() {
    setupTabs();
    setupNavMagnet();
    setupEntryAnimations();
    setupCountUp();
    setupScoreBars();
    setupFreqBars();
    setupChartLines();
    setupChartDonuts();
    setupSmoothScroll();
    setupMagnetic();
  }
})();
