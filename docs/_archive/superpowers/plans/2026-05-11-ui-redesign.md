# UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all 11 HTML templates with premium paid-product quality design — 4 new themes (Dark Polar Aurora, Light Vercel, Pastel Dreamy, Catppuccin Dev), animated aurora background, full animation system (page transitions, tabs, scroll reveal, charts, count-up, micro-interactions).

**Architecture:** Full CSS variable migration (`--bg-page`→`--bg-base`, `--text-primary`→`--text-1`, etc.) with backward-compat aliases during migration. themes.css rewritten with new 4 themes (glass→pastel, claude-dark→catppuccin). Animation framework injected globally in base.html via vanilla JS (IntersectionObserver + requestAnimationFrame). No Python changes.

**Tech Stack:** CSS Custom Properties, Vanilla JS (IntersectionObserver, rAF), Chart.js 4.4.0 (vendored), Pretendard Variable font, CSS `backdrop-filter`, CSS `@keyframes`, `color-mix()`

---

## Variable Migration Reference

Old → New (apply mechanically in each task):

| Old | New |
|-----|-----|
| `--bg-page` | `--bg-base` |
| `--text-primary` | `--text-1` |
| `--text-muted` | `--text-2` |
| `--text-nav` | `--text-3` |
| `--border` | `--border-subtle` |
| `--border-focus` | `--border-strong` |
| `--shadow-card` | `--shadow-sm` |
| `--table-head` | `--bg-elevated` |
| `--table-row-hover` | `rgba(var(--accent-rgb),.04)` |
| `--bg-card` | `--bg-card` (same name, new value) |
| `--accent-grad` | `linear-gradient(135deg, var(--accent), var(--accent-2))` |
| `body[data-theme="glass"]` | `body[data-theme="pastel"]` |
| `body[data-theme="claude-dark"]` | `body[data-theme="catppuccin"]` |
| theme: `glass` | theme: `pastel` |
| theme: `claude-dark` | theme: `catppuccin` |

---

### Task 1: CSS Foundation — themes.css, tokens.css, main.css

**Files:**
- Modify: `src/static/css/themes.css`
- Modify: `src/static/css/tokens.css`
- Modify: `src/static/css/main.css`

- [ ] **Step 1: Rewrite themes.css with 4 new themes + backward-compat aliases**

Replace the entire content of `src/static/css/themes.css` with:

```css
/* ============================================================================
 * SCAManager — 4-Theme Definitions (2026-05-11 UI Redesign)
 * 4 테마: dark (Polar Aurora) / light (Vercel) / pastel (Dreamy) / catppuccin (Dev)
 * ========================================================================== */

/* ── Dark — Polar Aurora ─────────────────────────────────────────────────── */
[data-theme="dark"], body:not([data-theme]) {
  --bg-base:        #07070f;
  --bg-card:        rgba(255,255,255,0.04);
  --bg-elevated:    #13131f;
  --bg-nav:         rgba(7,7,15,0.85);
  --bg-input:       rgba(255,255,255,0.06);
  --bg-input-focus: rgba(255,255,255,0.1);
  --text-1:         #f0f0f8;
  --text-2:         #8b8b9e;
  --text-3:         #6b6b7e;
  --accent:         #6366f1;
  --accent-2:       #a855f7;
  --accent-3:       #ec4899;
  --accent-hover:   #818cf8;
  --accent-rgb:     99,102,241;
  --pink:           #ec4899;
  --purple:         #a855f7;
  --border-subtle:  rgba(255,255,255,0.06);
  --border-strong:  rgba(255,255,255,0.14);
  --success:        #4ade80;
  --warning:        #f59e0b;
  --danger:         #f87171;
  --shadow-sm:      0 1px 3px rgba(0,0,0,.4), 0 0 0 1px rgba(255,255,255,.04);
  --shadow-md:      0 4px 24px rgba(0,0,0,.5);
  --shadow-lg:      0 8px 48px rgba(0,0,0,.6);
  --code-bg:        rgba(0,0,0,0.3);
  --grade-a:        #4ade80; --grade-b: #60a5fa; --grade-c: #fbbf24;
  --grade-d:        #fb923c; --grade-f: #f87171;

  /* aurora orb colors */
  --orb1: rgba(99,102,241,0.18);
  --orb2: rgba(168,85,247,0.14);
  --orb3: rgba(236,72,153,0.10);
  --orb4: rgba(59,130,246,0.12);

  /* settings page compat */
  --grad-gate:          linear-gradient(135deg,#6366f1,#4f46e5);
  --grad-merge:         linear-gradient(135deg,#06b6d4,#0891b2);
  --grad-notify:        linear-gradient(135deg,#fbbf24,#f59e0b);
  --grad-hook:          linear-gradient(135deg,#a855f7,#7c3aed);
  --title-gradient:     linear-gradient(135deg,#818cf8,#c084fc);
  --btn-gate-active-bg: rgba(99,102,241,.15);
  --btn-gate-active-bd: #6366f1;
  --btn-gate-active-tx: #818cf8;
  --save-btn-bg:        linear-gradient(135deg,#6366f1,#4f46e5);
  --save-btn-shadow:    rgba(99,102,241,.4);
  --hint-bg:            rgba(255,255,255,.03);
  --hint-border:        rgba(255,255,255,.05);
  --hook-btn-bg:        rgba(168,85,247,.1);
  --hook-btn-bd:        rgba(168,85,247,.3);
  --hook-btn-tx:        #c084fc;

  /* backward-compat aliases — remove after full migration */
  --bg-page:        var(--bg-base);
  --text-primary:   var(--text-1);
  --text-muted:     var(--text-2);
  --text-nav:       var(--text-3);
  --border:         var(--border-subtle);
  --border-focus:   var(--border-strong);
  --shadow-card:    var(--shadow-sm);
  --table-head:     var(--bg-elevated);
  --table-row-hover: rgba(99,102,241,0.04);
  --accent-grad:    linear-gradient(135deg,var(--accent),var(--accent-2));
}

/* ── Light — Vercel ──────────────────────────────────────────────────────── */
[data-theme="light"] {
  --bg-base:        #f6f6fd;
  --bg-card:        rgba(255,255,255,0.9);
  --bg-elevated:    #ffffff;
  --bg-nav:         rgba(246,246,253,0.85);
  --bg-input:       #f0f0f8;
  --bg-input-focus: #ffffff;
  --text-1:         #0f0f1a;
  --text-2:         #5c5c7a;
  --text-3:         #9090aa;
  --accent:         #4f46e5;
  --accent-2:       #7c3aed;
  --accent-3:       #db2777;
  --accent-hover:   #4338ca;
  --accent-rgb:     79,70,229;
  --pink:           #db2777;
  --purple:         #7c3aed;
  --border-subtle:  rgba(0,0,0,0.06);
  --border-strong:  rgba(0,0,0,0.14);
  --success:        #16a34a;
  --warning:        #d97706;
  --danger:         #dc2626;
  --shadow-sm:      0 1px 3px rgba(0,0,0,.05), 0 0 0 1px rgba(0,0,0,.04);
  --shadow-md:      0 4px 16px rgba(0,0,0,.08);
  --shadow-lg:      0 8px 32px rgba(0,0,0,.12);
  --code-bg:        #f0f0f8;
  --grade-a:        #16a34a; --grade-b: #2563eb; --grade-c: #d97706;
  --grade-d:        #ea580c; --grade-f: #dc2626;

  --orb1: rgba(79,70,229,0.07);
  --orb2: rgba(124,58,237,0.06);
  --orb3: rgba(219,39,119,0.05);
  --orb4: rgba(37,99,235,0.05);

  --grad-gate:          linear-gradient(135deg,#818cf8,#4f46e5);
  --grad-merge:         linear-gradient(135deg,#22d3ee,#0891b2);
  --grad-notify:        linear-gradient(135deg,#fcd34d,#f59e0b);
  --grad-hook:          linear-gradient(135deg,#c4b5fd,#7c3aed);
  --title-gradient:     linear-gradient(135deg,#4338ca,#7c3aed);
  --btn-gate-active-bg: rgba(79,70,229,.08);
  --btn-gate-active-bd: #4f46e5;
  --btn-gate-active-tx: #4f46e5;
  --save-btn-bg:        linear-gradient(135deg,#4f46e5,#7c3aed);
  --save-btn-shadow:    rgba(79,70,229,.25);
  --hint-bg:            #f9f9fb;
  --hint-border:        #e5e5e8;
  --hook-btn-bg:        rgba(124,58,237,.06);
  --hook-btn-bd:        rgba(124,58,237,.2);
  --hook-btn-tx:        #7c3aed;

  --bg-page:        var(--bg-base);
  --text-primary:   var(--text-1);
  --text-muted:     var(--text-2);
  --text-nav:       var(--text-3);
  --border:         var(--border-subtle);
  --border-focus:   var(--border-strong);
  --shadow-card:    var(--shadow-sm);
  --table-head:     var(--bg-elevated);
  --table-row-hover: rgba(79,70,229,0.04);
  --accent-grad:    linear-gradient(135deg,var(--accent),var(--accent-2));
}

/* ── Pastel — Dreamy Soft (replaces Glass) ───────────────────────────────── */
[data-theme="pastel"] {
  --bg-base:        #f0ecff;
  --bg-card:        rgba(255,255,255,0.72);
  --bg-elevated:    #ffffff;
  --bg-nav:         rgba(240,236,255,0.85);
  --bg-input:       rgba(255,255,255,0.6);
  --bg-input-focus: rgba(255,255,255,0.9);
  --text-1:         #1e0a4a;
  --text-2:         #6b4fa0;
  --text-3:         #a08cc0;
  --accent:         #8b5cf6;
  --accent-2:       #a78bfa;
  --accent-3:       #f472b6;
  --accent-hover:   #7c3aed;
  --accent-rgb:     139,92,246;
  --pink:           #f472b6;
  --purple:         #d946ef;
  --border-subtle:  rgba(139,92,246,0.12);
  --border-strong:  rgba(139,92,246,0.28);
  --success:        #059669;
  --warning:        #d97706;
  --danger:         #dc2626;
  --shadow-sm:      0 1px 3px rgba(139,92,246,.1), 0 0 0 1px rgba(139,92,246,.08);
  --shadow-md:      0 4px 16px rgba(139,92,246,.15);
  --shadow-lg:      0 8px 32px rgba(139,92,246,.2);
  --code-bg:        rgba(139,92,246,0.06);
  --grade-a:        #059669; --grade-b: #4f46e5; --grade-c: #d97706;
  --grade-d:        #ea580c; --grade-f: #dc2626;

  --orb1: rgba(167,139,250,0.28);
  --orb2: rgba(244,114,182,0.22);
  --orb3: rgba(217,70,239,0.16);
  --orb4: rgba(139,92,246,0.20);

  --grad-gate:          linear-gradient(135deg,#a78bfa,#8b5cf6);
  --grad-merge:         linear-gradient(135deg,#34d399,#059669);
  --grad-notify:        linear-gradient(135deg,#fcd34d,#f59e0b);
  --grad-hook:          linear-gradient(135deg,#f9a8d4,#ec4899);
  --title-gradient:     linear-gradient(135deg,#8b5cf6,#d946ef);
  --btn-gate-active-bg: rgba(139,92,246,.12);
  --btn-gate-active-bd: #8b5cf6;
  --btn-gate-active-tx: #7c3aed;
  --save-btn-bg:        linear-gradient(135deg,#8b5cf6,#7c3aed);
  --save-btn-shadow:    rgba(139,92,246,.35);
  --hint-bg:            rgba(139,92,246,.05);
  --hint-border:        rgba(139,92,246,.12);
  --hook-btn-bg:        rgba(244,114,182,.08);
  --hook-btn-bd:        rgba(244,114,182,.25);
  --hook-btn-tx:        #db2777;

  --bg-page:        var(--bg-base);
  --text-primary:   var(--text-1);
  --text-muted:     var(--text-2);
  --text-nav:       var(--text-3);
  --border:         var(--border-subtle);
  --border-focus:   var(--border-strong);
  --shadow-card:    var(--shadow-sm);
  --table-head:     var(--bg-elevated);
  --table-row-hover: rgba(139,92,246,0.04);
  --accent-grad:    linear-gradient(135deg,var(--accent),var(--accent-2));
}

/* ── Catppuccin — Dev Dark (replaces Claude-dark) ────────────────────────── */
[data-theme="catppuccin"] {
  --bg-base:        #1e1e2e;
  --bg-card:        rgba(30,30,46,0.9);
  --bg-elevated:    #313244;
  --bg-nav:         rgba(30,30,46,0.92);
  --bg-input:       #313244;
  --bg-input-focus: #45475a;
  --text-1:         #cdd6f4;
  --text-2:         #a6adc8;
  --text-3:         #7f849c;
  --accent:         #cba6f7;
  --accent-2:       #b4befe;
  --accent-3:       #f38ba8;
  --accent-hover:   #d0a8f8;
  --accent-rgb:     203,166,247;
  --pink:           #f38ba8;
  --purple:         #cba6f7;
  --border-subtle:  rgba(203,166,247,0.12);
  --border-strong:  rgba(203,166,247,0.28);
  --success:        #a6e3a1;
  --warning:        #f9e2af;
  --danger:         #f38ba8;
  --shadow-sm:      0 1px 3px rgba(0,0,0,.5), 0 0 0 1px rgba(203,166,247,.06);
  --shadow-md:      0 4px 24px rgba(0,0,0,.6);
  --shadow-lg:      0 8px 48px rgba(0,0,0,.7);
  --code-bg:        rgba(0,0,0,0.3);
  --grade-a:        #a6e3a1; --grade-b: #89b4fa; --grade-c: #f9e2af;
  --grade-d:        #fab387; --grade-f: #f38ba8;

  --orb1: rgba(203,166,247,0.12);
  --orb2: rgba(243,139,168,0.10);
  --orb3: rgba(137,180,250,0.09);
  --orb4: rgba(180,190,254,0.10);

  --grad-gate:          linear-gradient(135deg,#cba6f7,#b4befe);
  --grad-merge:         linear-gradient(135deg,#a6e3a1,#94e2d5);
  --grad-notify:        linear-gradient(135deg,#f9e2af,#fab387);
  --grad-hook:          linear-gradient(135deg,#f5c2e7,#cba6f7);
  --title-gradient:     linear-gradient(135deg,#cba6f7,#f38ba8);
  --btn-gate-active-bg: rgba(203,166,247,.15);
  --btn-gate-active-bd: #cba6f7;
  --btn-gate-active-tx: #cba6f7;
  --save-btn-bg:        linear-gradient(135deg,#cba6f7,#b4befe);
  --save-btn-shadow:    rgba(203,166,247,.4);
  --hint-bg:            rgba(203,166,247,.05);
  --hint-border:        rgba(203,166,247,.12);
  --hook-btn-bg:        rgba(243,139,168,.08);
  --hook-btn-bd:        rgba(243,139,168,.25);
  --hook-btn-tx:        #f38ba8;
  --table-row-hover:    rgba(203,166,247,0.06);

  --bg-page:        var(--bg-base);
  --text-primary:   var(--text-1);
  --text-muted:     var(--text-2);
  --text-nav:       var(--text-3);
  --border:         var(--border-subtle);
  --border-focus:   var(--border-strong);
  --shadow-card:    var(--shadow-sm);
  --table-head:     var(--bg-elevated);
  --accent-grad:    linear-gradient(135deg,var(--accent),var(--accent-2));
}
```

- [ ] **Step 2: Add animation tokens to tokens.css**

Open `src/static/css/tokens.css`. After the existing `--ease-spring` line, add:

```css
  /* ── Animation keyframe names (convenience refs) ─────────────────────── */
  --anim-page-in:   page-in 0.35s var(--ease-out) both;
  --anim-tab-in:    tab-in  0.25s var(--ease-out) both;
  --anim-reveal-up: reveal-up 0.4s var(--ease-out) both;
  --anim-badge-pop: badge-pop 0.4s var(--ease-spring) both;
  --anim-modal-in:  modal-in 0.25s var(--ease-out) both;
  --anim-toast-in:  toast-in 0.28s var(--ease-out) both;
  --anim-shimmer:   shimmer 1.4s infinite linear;
  --anim-float-a:   float-a 22s ease-in-out infinite alternate;
  --anim-float-b:   float-b 28s ease-in-out infinite alternate;
  --anim-float-c:   float-c 18s ease-in-out infinite alternate;
  --anim-float-d:   float-d 24s ease-in-out infinite alternate;
```

- [ ] **Step 3: Update main.css Tailwind custom variants (glass→pastel, claude-dark→catppuccin)**

Replace the content of `src/static/css/main.css` with:

```css
/* SCAManager Tailwind v4 entry — Hybrid: layout utilities + CSS var theming */

@import "tailwindcss";

/* Explicit source scan: Jinja2 templates + static JS */
@source "../../templates";
@source "../js";

/* 4-theme custom variants */
@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));
@custom-variant light (&:where([data-theme=light], [data-theme=light] *));
@custom-variant pastel (&:where([data-theme=pastel], [data-theme=pastel] *));
@custom-variant catppuccin (&:where([data-theme=catppuccin], [data-theme=catppuccin] *));
```

- [ ] **Step 4: Rebuild Tailwind dist**

```bash
cd f:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager
npm run build
```

Expected: `src/static/css/dist/tailwind.css` updated. No errors.

- [ ] **Step 5: Run tests to verify no breakage**

```bash
make test-fast
```

Expected: All tests pass. CSS changes are non-breaking (backward-compat aliases in themes.css preserve all old variable names).

- [ ] **Step 6: Commit**

```bash
git add src/static/css/themes.css src/static/css/tokens.css src/static/css/main.css src/static/css/dist/tailwind.css
git commit -m "feat(ui): CSS foundation — 4 new themes (Dark/Light/Pastel/Catppuccin) + animation tokens"
```

---

### Task 2: base.html — Theme switcher + CSS variable migration in <style> block

**Files:**
- Modify: `src/templates/base.html`

- [ ] **Step 1: Update THEMES JS object (glass→pastel, claude-dark→catppuccin)**

In `base.html`, find the `const THEMES = {` block (around line 596) and replace with:

```js
const THEMES = {
  dark:        { icon: '🌌', name: '다크' },
  light:       { icon: '☀️', name: '라이트' },
  pastel:      { icon: '🌸', name: '파스텔' },
  catppuccin:  { icon: '🐾', name: '개발자' }
};
```

- [ ] **Step 2: Update theme-option HTML in nav**

Find the `<div class="theme-dropdown"` block and replace its children:

```html
<div class="theme-dropdown" id="themeDropdown" role="menu">
  <div class="theme-option" data-theme="dark"       role="menuitem" tabindex="0">🌌 다크 오로라</div>
  <div class="theme-option" data-theme="light"      role="menuitem" tabindex="0">☀️ 라이트</div>
  <div class="theme-option" data-theme="pastel"     role="menuitem" tabindex="0">🌸 파스텔</div>
  <div class="theme-option" data-theme="catppuccin" role="menuitem" tabindex="0">🐾 개발자 다크</div>
</div>
```

- [ ] **Step 3: Update body[data-theme="glass"] → body[data-theme="pastel"] in <style> block**

In the `<style>` block of base.html, find every occurrence of `[data-theme="glass"]` and `[data-theme="claude-dark"]` and replace:

```
body[data-theme="glass"] .card           → body[data-theme="pastel"] .card
body[data-theme="glass"] .s-card         → body[data-theme="pastel"] .s-card
body[data-theme="glass"] .theme-dropdown → body[data-theme="pastel"] .theme-dropdown
body[data-theme="glass"] .nav-links.open → body[data-theme="pastel"] .nav-links.open
```

- [ ] **Step 4: Update CSS variable references inside base.html <style> block**

Find and replace all occurrences in the `<style>` block:

```
var(--bg-page)      → var(--bg-base)
var(--text-primary) → var(--text-1)
var(--text-muted)   → var(--text-2)
var(--text-nav)     → var(--text-3)
var(--border)       → var(--border-subtle)  [only in component CSS, not in border-focus references]
var(--shadow-card)  → var(--shadow-sm)
var(--table-head)   → var(--bg-elevated)
```

Note: Be careful with `var(--border)` — search for `var(--border)` exactly (not `var(--border-focus)` etc.).

Also update the body rule:
```css
body {
  /* change: */
  background-color: var(--bg-base);
  color: var(--text-1);
  /* ... rest unchanged */
}
```

- [ ] **Step 5: Update <body> tag default theme attribute (keep dark) + nav height**

In the `<style>` block, change nav height:
```css
nav {
  height: 56px;  /* was 52px */
  /* ... rest unchanged */
}
```

Also update mobile nav top offset:
```css
.nav-links.open {
  top: 56px;  /* was 52px */
  /* ... rest unchanged */
}
```

Also update login.html min-height reference (calc based on nav 56px not 52px) — that's in a separate task.

- [ ] **Step 6: Verify dev server renders all 4 themes correctly**

```bash
make run
```

Open http://localhost:8000/login — check all 4 themes via dropdown. No broken CSS variables (browser console should show 0 errors).

- [ ] **Step 7: Commit**

```bash
git add src/templates/base.html
git commit -m "feat(ui): base.html — theme switcher updated (glass→pastel, claude-dark→catppuccin) + CSS variable migration"
```

---

### Task 3: base.html — New nav, aurora background, animation framework

**Files:**
- Modify: `src/templates/base.html`

- [ ] **Step 1: Add aurora orb HTML + noise overlay**

Replace the `<body data-theme="dark">` opening tag and everything before `<nav>`:

```html
<body data-theme="dark">
  <!-- Aurora background (fixed, pointer-events:none, z-index:0) -->
  <div class="aurora" aria-hidden="true">
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>
    <div class="orb orb-4"></div>
  </div>
```

- [ ] **Step 2: Add aurora CSS to the <style> block**

Add after the `@media (prefers-reduced-motion: reduce)` block:

```css
/* ── Aurora 배경 ────────────────────────────────────────────────────────── */
.aurora {
  position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden;
}
.orb {
  position: absolute; border-radius: 50%;
  filter: blur(80px); will-change: transform;
}
.orb-1 {
  width: 600px; height: 600px; top: -200px; left: -100px;
  background: radial-gradient(circle, var(--orb1), transparent 70%);
  animation: var(--anim-float-a);
}
.orb-2 {
  width: 500px; height: 500px; top: 30%; right: -150px;
  background: radial-gradient(circle, var(--orb2), transparent 70%);
  animation: var(--anim-float-b);
}
.orb-3 {
  width: 400px; height: 400px; bottom: -100px; left: 30%;
  background: radial-gradient(circle, var(--orb3), transparent 70%);
  animation: var(--anim-float-c);
}
.orb-4 {
  width: 350px; height: 350px; top: 50%; right: 20%;
  background: radial-gradient(circle, var(--orb4), transparent 70%);
  animation: var(--anim-float-d);
}
@keyframes float-a { 0%{transform:translate(0,0)} 100%{transform:translate(60px,-80px)} }
@keyframes float-b { 0%{transform:translate(0,0)} 100%{transform:translate(-80px,60px)} }
@keyframes float-c { 0%{transform:translate(0,0)} 100%{transform:translate(40px,90px)} }
@keyframes float-d { 0%{transform:translate(0,0)} 100%{transform:translate(-50px,-70px)} }

/* noise texture overlay */
body::after {
  content: '';
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
  opacity: 0.03; mix-blend-mode: overlay;
}

/* page content above aurora */
nav, .container { position: relative; z-index: 1; }

/* ── Page-in animation ──────────────────────────────────────────────────── */
@keyframes page-in { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
@keyframes tab-in  { from{opacity:0;transform:translateX(-8px)} to{opacity:1;transform:translateX(0)} }
@keyframes reveal-up { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
@keyframes badge-pop { 0%{transform:scale(0.7)} 80%{transform:scale(1.05)} 100%{transform:scale(1)} }
@keyframes modal-in  { from{opacity:0;transform:scale(0.95) translateY(8px)} to{opacity:1;transform:scale(1) translateY(0)} }
@keyframes toast-in  { from{opacity:0;transform:translateX(24px)} to{opacity:1;transform:translateX(0)} }

.container { animation: var(--anim-page-in); }
.reveal { opacity: 0; }
.reveal.visible { animation: var(--anim-reveal-up); animation-delay: calc(var(--i,0) * 60ms); }
.tab-panel { display: none; }
.tab-panel.active { display: block; animation: var(--anim-tab-in); }
```

- [ ] **Step 3: Update nav HTML to new design (56px, glassmorphism, avatar, beta badge)**

Replace the entire `<nav>...</nav>` block with:

```html
<nav>
  <a class="nav-logo" href="/">
    <div class="nav-logo-icon">⚡</div>
    <strong>SCAManager</strong>
  </a>
  {% if current_user %}
  <button class="nav-hamburger" id="navHamburger" aria-label="{{ 'common.menu_aria' | i18n_args(locale | default('ko')) }}" aria-expanded="false">☰</button>
  <div class="nav-links" id="navLinks">
    <a class="nav-link" href="/">{{ 'header.overview' | i18n_args(locale | default('ko')) }}</a>
    <a class="nav-link" href="/dashboard">{{ 'header.dashboard' | i18n_args(locale | default('ko')) }}</a>
  </div>
  {% endif %}
  <div class="nav-spacer"></div>
  <span class="nav-badge">Beta</span>
  {% if current_user %}
  <div class="nav-user">
    <div class="theme-switcher" id="langSwitcher">
      <button class="theme-btn" id="langToggle" aria-label="언어 변경" aria-haspopup="true" aria-expanded="false">
        <span id="langIcon">🌍</span>
        <span id="langName">한국어</span>
        <span class="chevron">▾</span>
      </button>
      <div class="theme-dropdown" id="langDropdown" role="menu">
        <div class="lang-option" data-lang="en" role="menuitem" tabindex="0">🇺🇸 English</div>
        <div class="lang-option" data-lang="ko" role="menuitem" tabindex="0">🇰🇷 한국어</div>
        <div class="lang-option" data-lang="ja" role="menuitem" tabindex="0">🇯🇵 日本語</div>
      </div>
    </div>
    <form method="post" action="/auth/logout" style="display:inline;margin:0">
      <button type="submit" class="nav-logout-btn">{{ 'common.logout' | i18n_args(locale | default('ko')) }}</button>
    </form>
    <div class="nav-avatar">{{ (current_user.display_name or current_user.github_login or 'U')[0] | upper }}</div>
  </div>
  {% endif %}
  <div class="theme-switcher" id="themeSwitcher">
    <button class="theme-btn" id="themeToggle" aria-label="테마 변경" aria-haspopup="true" aria-expanded="false">
      <span id="themeIcon">🌌</span>
      <span id="themeName">다크</span>
      <span class="chevron">▾</span>
    </button>
    <div class="theme-dropdown" id="themeDropdown" role="menu">
      <div class="theme-option" data-theme="dark"       role="menuitem" tabindex="0">🌌 다크 오로라</div>
      <div class="theme-option" data-theme="light"      role="menuitem" tabindex="0">☀️ 라이트</div>
      <div class="theme-option" data-theme="pastel"     role="menuitem" tabindex="0">🌸 파스텔</div>
      <div class="theme-option" data-theme="catppuccin" role="menuitem" tabindex="0">🐾 개발자 다크</div>
    </div>
  </div>
</nav>
```

- [ ] **Step 4: Add nav-badge and nav-avatar CSS to <style> block**

Add after the existing `.nav-logout-btn` rules:

```css
/* ── Nav badge + avatar ─────────────────────────────────────────────────── */
.nav-badge {
  background: rgba(var(--accent-rgb),.15);
  border: 1px solid rgba(var(--accent-rgb),.3);
  color: var(--accent);
  font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: var(--radius-pill);
  letter-spacing: .04em;
}
.nav-avatar {
  width: 28px; height: 28px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #fff;
  border: 2px solid var(--border-subtle);
  flex-shrink: 0;
}

/* ── Updated nav CSS ────────────────────────────────────────────────────── */
nav {
  backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid var(--border-subtle);
  box-shadow: none;  /* remove old shadow */
}
.nav-logo-icon {
  width: 28px; height: 28px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(var(--accent-rgb),.4);
}
```

- [ ] **Step 5: Add animation JS framework at end of <script> block**

Before the closing `</script>` tag, add:

```js
// ── Animation framework ────────────────────────────────────────────────────
// Scroll reveal
(function() {
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e, idx) => {
      if (e.isIntersecting) {
        e.target.style.setProperty('--i', idx);
        e.target.classList.add('visible');
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
  document.querySelectorAll('.card, .s-card, .kpi-card, .reveal').forEach(el => {
    el.classList.add('reveal');
    io.observe(el);
  });
})();

// Count-up for KPI values
function countUp(el, duration) {
  const target = parseFloat(el.dataset.count || el.textContent.replace(/[^0-9.]/g,''));
  if (isNaN(target)) return;
  const suffix = el.dataset.suffix || '';
  const isFloat = String(target).includes('.');
  const start = performance.now();
  const tick = (now) => {
    const p = Math.min((now - start) / (duration || 1200), 1);
    const ease = 1 - Math.pow(1 - p, 3);
    const val = isFloat ? (ease * target).toFixed(1) : Math.round(ease * target).toLocaleString();
    el.textContent = val + suffix;
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
document.querySelectorAll('[data-count]').forEach(el => {
  const io2 = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) { countUp(el); io2.unobserve(el); }
  });
  io2.observe(el);
});

// Chart.js global animation defaults
if (typeof Chart !== 'undefined') {
  Chart.defaults.animation = { duration: 900, easing: 'easeOutQuart' };
  Chart.defaults.datasets.bar = Chart.defaults.datasets.bar || {};
  Chart.defaults.datasets.bar.animation = { from: 0 };
  Chart.defaults.datasets.doughnut = Chart.defaults.datasets.doughnut || {};
  Chart.defaults.datasets.doughnut.animation = { animateRotate: true, animateScale: true };
}

// Tab panel activation (for pages using .tab-btn + .tab-panel)
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.tab-panel').forEach(p => {
      const show = p.id === target;
      if (show) { p.classList.add('active'); p.offsetWidth; } // force reflow for re-animation
      else { p.classList.remove('active'); }
    });
  });
});
```

- [ ] **Step 6: Verify all 4 themes + animation work**

```bash
make run
```

Check: http://localhost:8000/ — aurora orbs visible, page-in animation on load, scroll reveal on cards.
Switch all 4 themes — orb colors change per theme. Console: 0 errors.

- [ ] **Step 7: Run tests**

```bash
make test-fast
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/templates/base.html
git commit -m "feat(ui): base.html — aurora background, new nav (56px/avatar/badge), animation framework"
```

---

### Task 4: login.html — Premium hero redesign

**Files:**
- Modify: `src/templates/login.html`

- [ ] **Step 1: Update scoped <style> block — replace all old CSS variables + add animations**

In login.html's `<style>` block, apply the variable mapping from the header table:
- `var(--text-primary)` → `var(--text-1)`
- `var(--text-muted)` → `var(--text-2)`
- `var(--accent-grad)` → `linear-gradient(135deg, var(--accent), var(--accent-2))`

Add new styles:

```css
  .login-wrap {
    min-height: calc(100dvh - 56px);  /* updated from 52px */
  }
  .login-card {
    background: var(--bg-card);
    backdrop-filter: blur(16px) saturate(150%);
    border: 1px solid var(--border-subtle);
    box-shadow: var(--shadow-md);
    animation: var(--anim-modal-in);
  }
  .login-logo {
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    box-shadow: 0 4px 20px rgba(var(--accent-rgb), .4);
    animation: var(--anim-badge-pop);
  }
  .login-title {
    background: linear-gradient(135deg, var(--text-1), var(--accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    color: transparent;
  }
  .login-sub { color: var(--text-2); }
```

- [ ] **Step 2: Update btn-github hover to use accent color**

```css
  .btn-github:hover {
    background: #32383f;
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(0,0,0,.3);
  }
```

- [ ] **Step 3: Add error/flash message animation**

```css
  .flash-msg {
    animation: var(--anim-toast-in);
  }
```

- [ ] **Step 4: Verify login page on all 4 themes**

```bash
make run
```

Check http://localhost:8000/login — gradient title, glass card, logo pop animation, all 4 themes look correct.

- [ ] **Step 5: Commit**

```bash
git add src/templates/login.html
git commit -m "feat(ui): login.html — gradient title, glass card, badge-pop animation"
```

---

### Task 5: overview.html — KPI summary + repo table redesign

**Files:**
- Modify: `src/templates/overview.html`

- [ ] **Step 1: Apply variable migration to scoped <style> block**

```
var(--text-primary)  → var(--text-1)
var(--text-muted)    → var(--text-2)
var(--border)        → var(--border-subtle)
```

- [ ] **Step 2: Add reveal animation to card + table rows**

Add to the `<style>` block:

```css
  .overview-repo-table tbody tr {
    position: relative;
    transition: background var(--dur-fast) var(--ease-out);
  }
  .overview-repo-table tbody tr::before {
    content: '';
    position: absolute; left: 0; top: 0; bottom: 0;
    width: 3px;
    background: linear-gradient(to bottom, var(--accent), var(--accent-2));
    transform: scaleY(0); transform-origin: top;
    transition: transform var(--dur-base) var(--ease-out);
  }
  .overview-repo-table tbody tr:hover::before { transform: scaleY(1); }
```

- [ ] **Step 3: Add data-count to KPI numbers in the overview header**

Find the repo count badge element in the HTML. If overview shows aggregate stats (e.g., total repos, avg score), add `data-count` attribute:

```html
<span class="repo-count" data-count="{{ repos | length }}">{{ repos | length }}</span>
```

- [ ] **Step 4: Add .reveal class to main card**

Find the `<div class="s-card">` or `<div class="card">` wrapping the table and add class `reveal`:

```html
<div class="s-card reveal">
```

- [ ] **Step 5: Update overview-title to gradient text**

In the `<style>` block:

```css
  .overview-title {
    background: linear-gradient(135deg, var(--text-1), var(--accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    color: transparent;
  }
```

- [ ] **Step 6: Verify**

```bash
make run
```

Check http://localhost:8000/ — gradient title, table row hover accent bar, scroll reveal on card.

- [ ] **Step 7: Commit**

```bash
git add src/templates/overview.html
git commit -m "feat(ui): overview.html — gradient title, table reveal animation, accent hover bar"
```

---

### Task 6: dashboard.html — Chart animations + KPI count-up

**Files:**
- Modify: `src/templates/dashboard.html`

- [ ] **Step 1: Apply variable migration to <style> block**

```
var(--text-primary)  → var(--text-1)
var(--text-muted)    → var(--text-2)
var(--border)        → var(--border-subtle)
var(--shadow-card)   → var(--shadow-sm)
```

Also replace `body[data-theme="glass"]` → `body[data-theme="pastel"]` and `body[data-theme="claude-dark"]` → `body[data-theme="catppuccin"]` in scoped styles (if any).

- [ ] **Step 2: Add data-count to KPI card value elements**

Find each `.dash-kpi` card and add `data-count` to the main value element. Example:

```html
<!-- Before -->
<div class="dash-kpi-val">{{ avg_score }}</div>

<!-- After -->
<div class="dash-kpi-val" data-count="{{ avg_score }}" data-suffix="">{{ avg_score }}</div>
```

Apply to all 5 KPI cards. For percentage KPIs, add `data-suffix="%"`.

- [ ] **Step 3: Add KPI card accent bottom line animation**

In the `<style>` block, add:

```css
  .dash-kpi {
    position: relative;
    transition: transform var(--dur-base) var(--ease-out),
                box-shadow var(--dur-base) var(--ease-out);
  }
  .dash-kpi:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }
  .dash-kpi::after {
    content: '';
    position: absolute; bottom: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--accent), var(--accent-2));
    border-radius: 0 0 var(--radius-card) var(--radius-card);
    transform: scaleX(0); transform-origin: left;
    transition: transform var(--dur-slow) var(--ease-out);
  }
  .dash-kpi.visible::after { transform: scaleX(1); }
```

- [ ] **Step 4: Add .reveal to each KPI card div**

```html
<div class="dash-kpi reveal">
```

- [ ] **Step 5: Chart.js animation — verify global defaults apply**

The animation defaults were set in base.html's script block (Task 3). Verify that charts in dashboard.html render with easeOutQuart animation. If dashboard.html defines a local Chart.js `animation: {}` override, remove it to let globals apply.

- [ ] **Step 6: Verify**

```bash
make run
```

Check http://localhost:8000/dashboard — KPI count-up on load, chart bars grow from 0, KPI card bottom line slides in.

- [ ] **Step 7: Commit**

```bash
git add src/templates/dashboard.html
git commit -m "feat(ui): dashboard.html — KPI count-up, chart animation, card reveal"
```

---

### Task 7: repo_detail.html — Score badges + analysis table

**Files:**
- Modify: `src/templates/repo_detail.html`

- [ ] **Step 1: Apply variable migration**

Same search-replace pattern: `--text-primary`→`--text-1`, `--text-muted`→`--text-2`, `--border`→`--border-subtle`, `--shadow-card`→`--shadow-sm`. Also update `[data-theme="glass"]` → `[data-theme="pastel"]` and `[data-theme="claude-dark"]` → `[data-theme="catppuccin"]` in scoped CSS.

- [ ] **Step 2: Add badge-pop animation to score/grade badges**

In `<style>` block:

```css
  .grade, .score-badge {
    animation: var(--anim-badge-pop);
  }
```

- [ ] **Step 3: Add table row hover accent bar**

```css
  .analysis-table tbody tr {
    position: relative;
    transition: background var(--dur-fast) var(--ease-out);
  }
  .analysis-table tbody tr::before {
    content: '';
    position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: linear-gradient(to bottom, var(--accent), var(--accent-2));
    transform: scaleY(0); transform-origin: top;
    transition: transform var(--dur-base) var(--ease-out);
  }
  .analysis-table tbody tr:hover::before { transform: scaleY(1); }
```

- [ ] **Step 4: Add chart re-build on theme change (already exists — verify)**

repo_detail.html already has `document.addEventListener('themechange', buildChart)`. Verify it still works after variable name changes. The `buildChart` function uses `getComputedStyle` to read CSS variables — no changes needed there.

- [ ] **Step 5: Add .reveal to cards and stats sections**

```html
<div class="s-card reveal">
```

- [ ] **Step 6: Verify**

```bash
make run
```

Navigate to a repo detail page — badges pop, table row accent bar on hover, chart re-builds on theme change.

- [ ] **Step 7: Commit**

```bash
git add src/templates/repo_detail.html
git commit -m "feat(ui): repo_detail.html — badge pop, table hover animation, reveal"
```

---

### Task 8: analysis_detail.html — Code review sections

**Files:**
- Modify: `src/templates/analysis_detail.html`

- [ ] **Step 1: Apply variable migration**

Same search-replace: `--text-primary`→`--text-1`, `--text-muted`→`--text-2`, `--border`→`--border-subtle`, `--shadow-card`→`--shadow-sm`.

- [ ] **Step 2: Add stagger reveal to issue cards**

In `<style>` block:

```css
  .issue-item, .review-section { }  /* already .reveal from base.html's IntersectionObserver */
```

In the HTML, add `reveal` class to issue items:

```html
<div class="issue-item reveal">
```

The IntersectionObserver in base.html will handle stagger via `--i` CSS variable.

- [ ] **Step 3: Add score badge pop animation**

```css
  .score-ring, .score-display {
    animation: var(--anim-badge-pop);
    animation-delay: 0.3s;
  }
```

- [ ] **Step 4: Add trend chart animation (already via Chart.js globals)**

Verify trend chart exists and uses Chart.js — no changes needed beyond global defaults from Task 3.

- [ ] **Step 5: Verify**

```bash
make run
```

Navigate to an analysis detail page — issue cards stagger-reveal on scroll, score badge pops, trend chart animates.

- [ ] **Step 6: Commit**

```bash
git add src/templates/analysis_detail.html
git commit -m "feat(ui): analysis_detail.html — stagger reveal, score badge pop animation"
```

---

### Task 9: add_repo.html — Form animations

**Files:**
- Modify: `src/templates/add_repo.html`

- [ ] **Step 1: Apply variable migration**

`--text-primary`→`--text-1`, `--text-muted`→`--text-2`, `--border`→`--border-subtle`.

- [ ] **Step 2: Add form input focus animations**

In `<style>` block:

```css
  .form-input, .form-select, input[type="text"], input[type="url"] {
    transition: border-color var(--dur-base) var(--ease-out),
                box-shadow var(--dur-base) var(--ease-out),
                background var(--dur-base) var(--ease-out);
  }
  .form-input:focus, input[type="text"]:focus, input[type="url"]:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(var(--accent-rgb), .15);
    background: var(--bg-input-focus);
  }
```

- [ ] **Step 3: Add card reveal animation**

```html
<div class="s-card reveal">
```

- [ ] **Step 4: Add page title gradient**

```css
  .page-header h1, .page-header h2 {
    background: linear-gradient(135deg, var(--text-1), var(--accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    color: transparent;
  }
```

- [ ] **Step 5: Verify**

```bash
make run
```

Check /repos/add — form focus glow, card reveal, gradient title.

- [ ] **Step 6: Commit**

```bash
git add src/templates/add_repo.html
git commit -m "feat(ui): add_repo.html — form focus glow animation, card reveal"
```

---

### Task 10: settings.html — Tab system + save bar

**Files:**
- Modify: `src/templates/settings.html`

- [ ] **Step 1: Apply variable migration**

`--text-primary`→`--text-1`, `--text-muted`→`--text-2`, `--border`→`--border-subtle`, `--shadow-card`→`--shadow-sm`. Replace `[data-theme="claude-dark"]` → `[data-theme="catppuccin"]`.

- [ ] **Step 2: Verify .tab-panel pattern is compatible**

Settings.html uses tab navigation. Check if it uses `.tab-panel` class. If it uses a different pattern (e.g., `.settings-section` + JS show/hide), update it to use `.tab-panel.active` pattern so the global tab animation from base.html applies.

If settings.html has its own JS show/hide:

```js
// Find existing tab click handler and update to add/remove .active class:
function showSection(id) {
  document.querySelectorAll('.settings-section').forEach(s => s.classList.remove('active', 'tab-panel'));
  document.querySelectorAll('.settings-nav-btn').forEach(b => b.classList.remove('active'));
  const section = document.getElementById(id);
  if (section) {
    section.classList.add('tab-panel', 'active');
    section.offsetWidth; // force reflow for re-animation
  }
}
```

- [ ] **Step 3: Add card reveal**

```html
<div class="s-card reveal">
```

- [ ] **Step 4: Add save bar slide-up animation**

```css
  .save-bar {
    animation: save-bar-in 0.3s var(--ease-out) both;
  }
  @keyframes save-bar-in {
    from { transform: translateY(100%); opacity: 0; }
    to   { transform: translateY(0);   opacity: 1; }
  }
```

- [ ] **Step 5: Update toggle switch animation**

```css
  .toggle-switch .slider {
    transition: background var(--dur-base) var(--ease-out),
                transform var(--dur-base) var(--ease-out);
  }
  input:checked + .slider { background: var(--accent); }
  input:checked + .slider::before { transform: translateX(20px); }
```

- [ ] **Step 6: Verify**

```bash
make run
```

Check /settings — card reveal, section tab animation, save bar slide-up, toggle transitions.

- [ ] **Step 7: Commit**

```bash
git add src/templates/settings.html
git commit -m "feat(ui): settings.html — tab animation, save bar slide-up, toggle transitions"
```

---

### Task 11: Admin templates (3 files)

**Files:**
- Modify: `src/templates/admin_rls_audit.html`
- Modify: `src/templates/admin_tenants.html`
- Modify: `src/templates/admin_operations.html`

- [ ] **Step 1: Apply variable migration to all 3 admin templates**

For each file, apply the same search-replace:
```
var(--text-primary)  → var(--text-1)
var(--text-muted)    → var(--text-2)
var(--border)        → var(--border-subtle)
var(--shadow-card)   → var(--shadow-sm)
[data-theme="glass"] → [data-theme="pastel"]
[data-theme="claude-dark"] → [data-theme="catppuccin"]
```

- [ ] **Step 2: Add table row hover accent bar to admin tables**

In each admin template's `<style>` block:

```css
  table tbody tr {
    position: relative;
    transition: background var(--dur-fast) var(--ease-out);
  }
  table tbody tr::before {
    content: '';
    position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: linear-gradient(to bottom, var(--accent), var(--accent-2));
    transform: scaleY(0); transform-origin: top;
    transition: transform var(--dur-base) var(--ease-out);
  }
  table tbody tr:hover::before { transform: scaleY(1); }
```

- [ ] **Step 3: Add .reveal to card containers**

```html
<div class="s-card reveal">
```

- [ ] **Step 4: Add page title gradient**

```css
  .page-header h1, .page-header h2 {
    background: linear-gradient(135deg, var(--text-1), var(--accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    color: transparent;
  }
```

- [ ] **Step 5: Verify**

```bash
make run
```

Check /admin/* — table row hover accent bar, card reveal, gradient title.

- [ ] **Step 6: Commit**

```bash
git add src/templates/admin_rls_audit.html src/templates/admin_tenants.html src/templates/admin_operations.html
git commit -m "feat(ui): admin templates — table animation, card reveal, gradient titles"
```

---

### Task 12: Final cleanup — Remove backward-compat aliases

**Files:**
- Modify: `src/static/css/themes.css`

- [ ] **Step 1: Verify all templates use new variable names**

Run this to find any remaining old variable references across all templates:

```bash
grep -rn "var(--bg-page)\|var(--text-primary)\|var(--text-muted)\|var(--text-nav)\b\|var(--border)\b\|var(--shadow-card)\|var(--table-head)\|data-theme=\"glass\"\|data-theme=\"claude-dark\"" src/templates/
```

Expected output: 0 matches. If any found, fix them before continuing.

- [ ] **Step 2: Also check base.html <style> block**

```bash
grep -n "var(--bg-page)\|var(--text-primary)\|var(--text-muted)\|data-theme=\"glass\"\|data-theme=\"claude-dark\"" src/templates/base.html
```

Expected: 0 matches.

- [ ] **Step 3: Remove backward-compat alias blocks from themes.css**

In each of the 4 theme blocks in `themes.css`, delete the `/* backward-compat aliases */` section:

```
  /* backward-compat aliases — remove after full migration */
  --bg-page:        var(--bg-base);
  --text-primary:   var(--text-1);
  --text-muted:     var(--text-2);
  --text-nav:       var(--text-3);
  --border:         var(--border-subtle);
  --border-focus:   var(--border-strong);
  --shadow-card:    var(--shadow-sm);
  --table-head:     var(--bg-elevated);
  --table-row-hover: rgba(...);
  --accent-grad:    ...;
```

Remove these lines from all 4 theme blocks.

- [ ] **Step 4: Run full test suite**

```bash
make test
```

Expected: All tests pass.

- [ ] **Step 5: Run dev server final check — all 4 themes**

```bash
make run
```

Navigate to: `/login`, `/`, `/dashboard`, `/repos/add`, `/settings`, one admin page.
Switch to each of the 4 themes on each page.
Expected: All pages render correctly, no broken CSS variables, all animations work.

- [ ] **Step 6: Commit**

```bash
git add src/static/css/themes.css
git commit -m "chore(ui): remove backward-compat CSS variable aliases — migration complete"
```

---

## Post-Implementation Checklist

- [ ] `make test` — all tests pass
- [ ] `make lint` — 0 errors
- [ ] All 4 themes verified on: login, overview, dashboard, repo_detail, analysis_detail, add_repo, settings, admin
- [ ] Mobile (768px) verified — nav hamburger, container padding, WCAG ≥44px tap targets preserved
- [ ] `prefers-reduced-motion` verified — no animations at OS level
- [ ] Chart.js animations verified — bars grow, line draws, donut rotates
- [ ] KPI count-up verified on dashboard
- [ ] Page-in animation verified — every page load has fade+slide
- [ ] PR created with 정책 11 8-combination checklist
