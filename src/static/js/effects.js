/* ============================================================================
   SCAManager · Effects controller
   ----------------------------------------------------------------------------
   - Stagger entry animations via IntersectionObserver
   - Count-up animation for KPI numbers
   - Score-bar / frequency-bar grow-in
   - SVG chart line draw + donut segment grow
   - Smooth in-page scroll
   All effects respect [data-motion="still"] and prefers-reduced-motion.

   hx-boost 재실행: init() 은 최초 로드 1회 + htmx:afterSettle / htmx:historyRestore
   마다 재실행 (remove-before-add 단일 슬롯 document._fxEffectsHandler). body swap 후
   애니메이션이 재생되지 않던 고착(opacity:0 / 0%)을 봉인한다 (U2). 부분 swap 재애니메이션은
   `seen` WeakMap(노드→effect 태그 집합) 멱등 가드로 차단 — 각 setup 은 헬퍼 `freshOnly(nodeList,
   tag)` 로 해당 effect 태그가 미처리한 노드만 조회·등록해 반환한다. effect 마다 독립적으로 새로
   삽입된 DOM 노드만 처리하고 잔존 노드는 건너뛴다(한 노드를 여러 effect 가 대상으로 삼아도 각 1회).
   hx-boost re-run: init() runs once on first load + on every htmx:afterSettle /
   htmx:historyRestore (single-slot remove-before-add via document._fxEffectsHandler),
   fixing the post-body-swap animation freeze (U2). Each setup uses the helper `freshOnly(nodeList,
   tag)` to fetch, register, and return only the nodes this effect tag has not yet processed, so the `seen`
   WeakMap (node → set of effect tags) keeps re-runs idempotent per-effect — only freshly inserted
   DOM nodes are processed and surviving nodes are skipped (a node targeted by multiple effects is
   handled once by EACH).
   ========================================================================== */
(function () {
  "use strict";

  const reduced = () =>
    document.documentElement.getAttribute("data-motion") === "still" ||
    matchMedia("(prefers-reduced-motion: reduce)").matches;

  // 노드별 처리 완료 effect 태그 집합 — 재실행 멱등 가드. 새 DOM 노드(swap)는 미포함 → 처리됨.
  // effect 마다 독립 태그로 추적 — 한 노드를 여러 effect 가 대상으로 삼아도(예: .repo-card 는
  // entry + magnetic 양쪽) 각 effect 가 독립적으로 1회만 처리한다 (공유 집합 충돌 방지).
  // Per-node set of completed effect tags — re-run idempotency guard. New DOM nodes (swap) are
  // absent → processed. Tracked per-effect so a node targeted by multiple effects (e.g. .repo-card
  // by both entry + magnetic) is processed exactly once by EACH effect (no shared-set collision).
  const seen = new WeakMap();

  // 안전망(onceInView) 누적 방지: init() 에서 일괄 dispose 하지 않는다. effects.js 는 <body> 외부
  // 스크립트라 hx-boost swap 마다 IIFE 가 재실행(즉시 init) + htmx:afterSettle 로 init 이 한 번 더
  // 호출된다(nav 당 2~3회). init 첫 줄에서 직전 안전망을 일괄 dispose 하면, 같은 closure 의
  // freshOnly(seen) 이 이미 처리한 노드를 EMPTY 로 반환해 재등록을 막아 → count-up 이 observer·리스너
  // 없이 "0" pre-fill 에 영구 고착됐다(Codex P1 회귀). 게다가 _disposers 는 IIFE 재실행마다 fresh 라
  // 이전 nav 의 누수도 못 잡았다. 대신 scroll/resize 리스너는 sweep 의 `!el.isConnected` 검사가
  // 자가 정리한다(다음 scroll/resize 때 detached 노드를 pending 에서 제거 → 비면 리스너 해제).
  // No blanket dispose in init(): effects.js is an external <body> script, so the IIFE re-executes on
  // every hx-boost swap (immediate init) AND htmx:afterSettle fires init again (2-3x per nav). Tearing
  // down the prior safety net at init start left count-up nodes with no observer/listener — the same
  // closure's freshOnly(seen) returns EMPTY for already-seen nodes, blocking re-registration → "0"
  // pre-fill sticks forever (Codex P1 regression). Instead, sweep's `!el.isConnected` check self-cleans
  // the scroll/resize listeners (detached nodes are dropped from pending → listeners released when empty).

  // 해당 effect(tag)가 아직 처리하지 않은 노드만 반환 + 처리 표시 (중복 애니메이션/리스너 방지).
  // Return only nodes this effect (tag) has not yet processed + mark them (no duplicate anim/listener).
  function freshOnly(nodeList, tag) {
    const out = [];
    nodeList.forEach((el) => {
      let tags = seen.get(el);
      if (!tags) {
        tags = new Set();
        seen.set(el, tags);
      }
      if (tags.has(tag)) return;
      tags.add(tag);
      out.push(el);
    });
    return out;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // hx-boost body swap / 뒤로가기 복원 후 재초기화 — remove-before-add 단일 슬롯 패턴.
  // Re-initialize after hx-boost body swap / back-nav restore — remove-before-add single slot.
  if (document._fxEffectsHandler) {
    document.removeEventListener("htmx:afterSettle", document._fxEffectsHandler);
    document.removeEventListener("htmx:historyRestore", document._fxEffectsHandler);
  }
  document._fxEffectsHandler = init;
  document.addEventListener("htmx:afterSettle", document._fxEffectsHandler);
  document.addEventListener("htmx:historyRestore", document._fxEffectsHandler);

  /* ----- shared IntersectionObserver factory ------------------------------ */
  function onceInView(elements, callback, opts = { threshold: 0.15, rootMargin: "0px 0px -60px 0px" }) {
    if (!("IntersectionObserver" in window)) {
      elements.forEach((el) => callback(el));
      return;
    }
    // fired 가드 — IO 콜백과 아래 안전망의 중복 실행 방지(요소당 1회). pending = 아직 실행 안 된 요소.
    // fired guard prevents double-run between IO callback and safety net; pending = not-yet-fired set.
    const fired = new WeakSet();
    const pending = new Set(elements);
    const fire = (el) => {
      if (fired.has(el)) return;
      fired.add(el);
      pending.delete(el);
      callback(el);
    };
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          fire(e.target);
          io.unobserve(e.target);
        }
      });
    }, opts);
    elements.forEach((el) => io.observe(el));
    // 🔴 안전망: hx-boost body swap race / IntersectionObserver 콜백 영구 미발동 시 "0" 으로
    // pre-fill 된 count-up 숫자(점수 등)가 고착된다(운영 사고 2026-06-18). 화면 안의 미실행 요소를
    // 강제 실행하되 one-shot 이 아니라 scroll/resize 에도 지속 sweep — 처음엔 화면 밖이던 아래쪽
    // repo 카드/차트/카운터가 스크롤로 보일 때도 복구한다(Codex P2). pending 이 비면 리스너 해제.
    // Safety net: if the IO callback never fires (hx-boost swap race / permanent miss), the
    // "0"-prefilled count-up sticks. Force-run in-viewport elements, and keep sweeping on
    // scroll/resize (not one-shot) so below-fold elements recover when scrolled into view.
    const sweep = () => {
      const vh = window.innerHeight || document.documentElement.clientHeight;
      pending.forEach((el) => {
        // detached(hx-boost swap 으로 분리된) 요소는 pending 에서 제거 — rect 가 0 이라 영원히
        // 미발동해 scroll/resize 리스너가 해제되지 않고 누적(메모리 누수)되는 것을 차단(Codex P2).
        // Drop detached elements (removed by hx-boost swap): their rect is 0 so they never fire
        // and would keep the scroll/resize listeners alive forever (Codex P2).
        if (!el.isConnected) {
          pending.delete(el);
          io.unobserve(el);
          return;
        }
        const r = el.getBoundingClientRect();
        if (r.top < vh && r.bottom > 0) {
          fire(el);
          io.unobserve(el);
        }
      });
      if (pending.size === 0) {
        window.removeEventListener("scroll", sweep);
        window.removeEventListener("resize", sweep);
      }
    };
    requestAnimationFrame(() => requestAnimationFrame(() => {
      sweep();
      if (pending.size > 0) {
        window.addEventListener("scroll", sweep, { passive: true });
        window.addEventListener("resize", sweep, { passive: true });
      }
    }));
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

    const targets = freshOnly(
      document.querySelectorAll(
        ".fx, .kpi, .principle, .full-card, .repo-card, .demo-grid, .detail-hero, .swatch, .tk-card, .freq-row, .reason-row, .breakdown__row, .issue, .pager, .alert, .section__head, .frame"
      ),
      "entry"
    );
    targets.forEach((el) => el.classList.add("fx-enter"));

    if (reduced()) {
      targets.forEach((el) => el.classList.add("is-in-view"));
      return;
    }

    onceInView(targets, (el) => {
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
    const candidates = freshOnly(
      document.querySelectorAll(".kpi__value, .repo-card__score, .detail-hero__num, .reason-row__count, .freq-row__count, .breakdown__val"),
      "countup"
    );
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
    const fresh = freshOnly(document.querySelectorAll(".score-bar"), "scorebar");
    fresh.forEach((bar) => {
      const inline = bar.style.getPropertyValue("--sb-pct").trim();
      if (!inline) return;
      bar.dataset.sbPct = inline;
      bar.style.setProperty("--sb-pct", "0%");
    });
    const bars = fresh.filter((b) => b.dataset.sbPct);
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
    const fresh = freshOnly(document.querySelectorAll(".freq-row__bar-fill"), "freqbar");
    fresh.forEach((fill) => {
      const target = fill.style.width;
      fill.dataset.targetWidth = target || "100%";
      fill.style.width = "0%";
    });
    const fills = fresh.filter((f) => f.dataset.targetWidth);
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
    const fresh = freshOnly(document.querySelectorAll("svg path[d]"), "chartline");
    fresh.forEach((path) => {
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
    const paths = fresh.filter((p) => p.dataset.len);
    if (reduced()) {
      paths.forEach((p) => (p.style.strokeDashoffset = "0"));
      return;
    }
    const svgs = Array.from(new Set(paths.map((p) => p.closest("svg")).filter(Boolean)));
    onceInView(svgs, (svg) => {
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
    });
  }

  /* ----- 6. SVG donut segments grow -------------------------------------- */
  function setupChartDonuts() {
    const donutSvgs = freshOnly(
      Array.from(document.querySelectorAll("svg")).filter(
        (svg) => svg.querySelectorAll("circle[stroke-dasharray]").length >= 2
      ),
      "donut"
    );
    donutSvgs.forEach((svg) => {
      svg.querySelectorAll("circle[stroke-dasharray]").forEach((seg) => {
        const orig = seg.getAttribute("stroke-dasharray");
        if (!orig) return;
        seg.dataset.dasharray = orig;
        seg.setAttribute("stroke-dasharray", "0 9999");
      });
    });
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

  /* ----- 7. Smooth scroll for in-page anchors ---------------------------- */
  function setupSmoothScroll() {
    freshOnly(document.querySelectorAll('a[href^="#"]'), "smoothscroll").forEach((a) => {
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

  /* ----- 8. Subtle magnetic hover on cards ------------------------------- */
  function setupMagnetic() {
    if (reduced()) return;
    const targets = freshOnly(document.querySelectorAll(".kpi, .repo-card, .principle"), "magnetic");
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
    // 일괄 dispose 없음 — 사유는 상단 `seen`/안전망 주석 참조 (Codex P1 회귀 가드).
    // No blanket dispose here — see the safety-net comment above (Codex P1 regression guard).
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
