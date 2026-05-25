# UI Redesign Design Spec — SCAManager
**Date**: 2026-05-11  
**Status**: Approved by user

---

## 1. Overview

Complete visual overhaul of all 11 HTML templates. Target quality: **premium paid-product** (사용자 표현: "유료로도 사용할만큼의 디자인"). Strategy: **Full Migration** — CSS variable names change to mockup-standard, all template references updated.

---

## 2. Design System

### 2.1 CSS Variables (Full Migration)

Old name → New name (all templates must be updated):

| Old | New |
|-----|-----|
| `--bg-page` | `--bg-base` |
| `--bg-card` | `--bg-card` (unchanged) |
| `--text-primary` | `--text-1` |
| `--text-muted` | `--text-2` |
| `--text-nav` | `--text-3` |
| `--accent` | `--accent` (unchanged) |
| `--shadow-card` | `--shadow-sm` / `--shadow-md` |
| `--bg-nav` | `--bg-nav` (new value: `rgba(10,10,15,0.85)`) |

New additions: `--bg-elevated`, `--accent-2`, `--accent-3`, `--pink`, `--purple`, `--success`, `--warning`, `--danger`, `--border-subtle`, `--border-strong`.

### 2.2 Four Themes

All themes retained. Glass → Pastel, Claude-dark → Catppuccin.

#### Dark — Polar Aurora
```css
--bg-base: #07070f;
--bg-card: rgba(255,255,255,0.04);
--bg-elevated: #13131f;
--bg-nav: rgba(7,7,15,0.85);
--text-1: #f0f0f8;
--text-2: #8b8b9e;
--text-3: #6b6b7e;
--accent: #6366f1;
--accent-2: #a855f7;
--pink: #ec4899;
--border-subtle: rgba(255,255,255,0.06);
```

#### Light — Vercel
```css
--bg-base: #f6f6fd;
--bg-card: rgba(255,255,255,0.9);
--bg-elevated: #ffffff;
--bg-nav: rgba(246,246,253,0.85);
--text-1: #0f0f1a;
--text-2: #5c5c7a;
--text-3: #9090aa;
--accent: #4f46e5;
--accent-2: #7c3aed;
--border-subtle: rgba(0,0,0,0.06);
```

#### Pastel — Dreamy Soft (replaces Glass)
```css
--bg-base: #f0ecff;
--bg-card: rgba(255,255,255,0.72);
--bg-elevated: #ffffff;
--bg-nav: rgba(240,236,255,0.85);
--text-1: #1e0a4a;
--text-2: #6b4fa0;
--text-3: #a08cc0;
--accent: #8b5cf6;
--accent-2: #a78bfa;
--purple: #d946ef;
--pink: #f472b6;
--border-subtle: rgba(139,92,246,0.12);
```

#### Catppuccin — Dev Dark (replaces Claude-dark)
```css
--bg-base: #1e1e2e;
--bg-card: rgba(30,30,46,0.9);
--bg-elevated: #313244;
--bg-nav: rgba(30,30,46,0.92);
--text-1: #cdd6f4;
--text-2: #a6adc8;
--text-3: #7f849c;
--accent: #cba6f7;
--accent-2: #b4befe;
--accent-3: #89b4fa;
--pink: #f38ba8;
--success: #a6e3a1;
--warning: #f9e2af;
--danger: #f38ba8;
--border-subtle: rgba(203,166,247,0.12);
```

### 2.3 Background System

Every page has a layered background:
1. **Base color** — `--bg-base` solid fill
2. **Aurora orbs** — 4 radial-gradient `div.orb` elements, `position:fixed`, `pointer-events:none`, `z-index:0`. Each orb uses a distinct `@keyframes` (float-a/b/c/d) with different translate ranges and durations (18s–28s), `animation-timing-function: ease-in-out`, `animation-direction: alternate`.
3. **Noise texture** — SVG `feTurbulence` filter as `background-image` overlay at 3% opacity, `mix-blend-mode: overlay`.
4. **Grid overlay** — for Pastel and Catppuccin themes: `background-image: linear-gradient(rgba(...) 1px, transparent 1px)` at 5% opacity.

All page content sits on `z-index: 1+`.

### 2.4 Typography

- Font: `Pretendard Variable` (CDN) → fallback to `system-ui`
- Page titles: gradient text — `background: linear-gradient(135deg, var(--text-1), var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;`
- Body: `--text-1` primary, `--text-2` secondary, `--text-3` placeholder/metadata

### 2.5 Navigation

- Height: 56px (was 52px)
- Background: `--bg-nav` + `backdrop-filter: blur(20px) saturate(180%)`
- Bottom border: `1px solid var(--border-subtle)`
- Logo icon: `28×28px`, `border-radius: 8px`, gradient fill, `box-shadow: 0 2px 8px rgba(var(--accent-rgb),.4)`
- Nav links: `color: var(--text-3)` default → `var(--text-1)` active, `background: rgba(255,255,255,.1)` active pill
- Right section: Beta badge (pill style), theme switcher (pill button), avatar circle

### 2.6 Cards

- Background: `--bg-card`
- `backdrop-filter: blur(12px) saturate(150%)`
- Border: `1px solid var(--border-subtle)`
- `border-radius: 16px`
- Hover: top-edge gradient accent bar (`::before` pseudo, `opacity: 0→1 transition 0.3s`)
- `box-shadow: var(--shadow-sm)` default → `var(--shadow-md)` hover

### 2.7 KPI Cards

4-column grid. Each card:
- Gradient icon background
- Metric value (large, `--text-1`)
- Label (`--text-2`)
- Trend indicator badge (green/red pill)
- Bottom accent line: `3px solid` with gradient, animates width `0→100%` on mount

---

## 3. Animation System

All animations use `prefers-reduced-motion: reduce` guard — motion disabled when user requests it.

### 3.1 Page Load / Route Transition

Technique: CSS class `.page-enter` added to `<main>` on every page load via small inline `<script>` at body end.

```css
@keyframes page-in {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
main { animation: page-in 0.35s cubic-bezier(0.16, 1, 0.3, 1) both; }
```

All Jinja2 template `{% block content %}` renders inside `<main>`, so every page gets this automatically from `base.html`.

### 3.2 Tab / Section Transitions

Any `<div class="tab-panel">` that becomes active:
```css
@keyframes tab-in {
  from { opacity: 0; transform: translateX(-8px); }
  to   { opacity: 1; transform: translateX(0); }
}
.tab-panel.active { animation: tab-in 0.25s cubic-bezier(0.16, 1, 0.3, 1) both; }
```

JS: on tab click, remove `active` from all panels → set `active` on target (re-triggers animation by forcing reflow: `el.offsetWidth`).

### 3.3 Card / Element Scroll Reveal

`IntersectionObserver` watches all `.card`, `.kpi-card`, `.repo-row` elements. When intersecting:

```css
@keyframes reveal-up {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}
.reveal { opacity: 0; }
.reveal.visible { animation: reveal-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) both; }
```

Stagger: `animation-delay: calc(var(--i) * 60ms)` where `--i` is set via JS `el.style.setProperty('--i', index)`.

### 3.4 KPI Number Count-Up

On page load (or when KPI cards enter viewport via IntersectionObserver):

```js
function countUp(el, target, duration = 1200) {
  const start = performance.now();
  const update = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    el.textContent = Math.round(ease * target).toLocaleString();
    if (progress < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}
```

All `.kpi-value[data-count]` elements get count-up on load.

### 3.5 Chart Animations

Chart.js (already used in dashboard) animation config added globally in `base.html`:

```js
Chart.defaults.animation = {
  duration: 900,
  easing: 'easeOutQuart',
};
Chart.defaults.datasets.bar.animation = {
  from: 0, // bars grow from 0
};
Chart.defaults.datasets.line.animation = {
  tension: { duration: 1000, easing: 'linear', from: 1, to: 0 }, // line draw-in
};
Chart.defaults.datasets.doughnut.animation = {
  animateRotate: true,
  animateScale: true,
};
```

### 3.6 Micro-interactions

| Element | Animation |
|---------|-----------|
| Buttons | `transform: scale(0.97)` on `:active`, `transition: 0.1s` |
| Nav links | `background` + `color` transition `0.18s` |
| Cards | `transform: translateY(-2px)` + shadow on hover, `transition: 0.2s` |
| Table rows | left accent bar slides in (`transform: scaleY(0)→scaleY(1)`) on hover |
| Form inputs | border glow (`box-shadow`) on `:focus`, `transition: 0.2s` |
| Score badges | pulse animation once on load: `@keyframes badge-pop { 0%{transform:scale(0.7)} 80%{transform:scale(1.05)} 100%{transform:scale(1)} }` |
| Theme switch button | `transform: rotate(20deg)` on click, resets `0.3s` |

### 3.7 Loading / Skeleton States

Skeleton screens for async-loaded content (repo list, analysis results):

```css
@keyframes shimmer {
  from { background-position: -200% 0; }
  to   { background-position:  200% 0; }
}
.skeleton {
  background: linear-gradient(90deg, var(--bg-elevated) 25%, var(--bg-card) 50%, var(--bg-elevated) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
  border-radius: 6px;
}
```

### 3.8 Modal / Drawer Animations

```css
@keyframes modal-in {
  from { opacity: 0; transform: scale(0.95) translateY(8px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}
.modal { animation: modal-in 0.25s cubic-bezier(0.16, 1, 0.3, 1) both; }
.overlay { animation: fade-in 0.2s ease both; }
```

### 3.9 Toast / Alert Animations

Slide in from top-right, auto-dismiss with fade-out:

```css
@keyframes toast-in  { from { opacity:0; transform: translateX(24px); } to { opacity:1; transform:translateX(0); } }
@keyframes toast-out { from { opacity:1; } to { opacity:0; transform: translateX(24px); } }
```

### 3.10 Aurora Orb Keyframes

4 distinct float keyframes to prevent synchronization artifacts:

```css
@keyframes float-a { 0%{transform:translate(0,0)} 100%{transform:translate(60px,-80px)} }
@keyframes float-b { 0%{transform:translate(0,0)} 100%{transform:translate(-80px,60px)} }
@keyframes float-c { 0%{transform:translate(0,0)} 100%{transform:translate(40px,90px)} }
@keyframes float-d { 0%{transform:translate(0,0)} 100%{transform:translate(-50px,-70px)} }
```

Durations: 22s / 28s / 18s / 24s. `animation-direction: alternate`, `animation-iteration-count: infinite`.

---

## 4. Page Scope

10 implementation PRs:

| PR | Pages | Key Changes |
|----|-------|-------------|
| 1 | `base.html` | New nav, CSS variable migration, aurora background, animation framework |
| 2 | `login.html` | Hero section, gradient headline, animated orbs, card glassmorphism |
| 3 | `overview.html` | KPI cards with count-up, repo table with reveal animation |
| 4 | `dashboard.html` | Chart.js animation config, analysis history table |
| 5 | `repo_detail.html` | Analysis runs list, score badges with pop animation |
| 6 | `analysis_detail.html` | Code review sections, issue cards with stagger reveal |
| 7 | `add_repo.html` | Form fields with focus animations, stepper UI |
| 8 | `settings/` | Card tabs with tab-in animation, toggle switches |
| 9 | `admin/` | Admin table, stats with count-up |
| 10 | `tokens.css` + `themes.css` refactor | Full variable rename, 4-theme definitions, animation variables |

---

## 5. File Changes

### Modified
- `src/static/css/themes.css` — 4 new theme definitions, animation base styles
- `src/static/css/tokens.css` — new tokens (`--duration-fast: 0.18s`, `--duration-base: 0.3s`, `--ease-out: cubic-bezier(0.16,1,0.3,1)`)
- `src/templates/base.html` — new nav, aurora HTML, page-in animation, Chart.js defaults, IntersectionObserver, count-up init
- All 9 page templates — CSS variable references updated, classes updated

### No Change
- `src/templates/base.html` Jinja2 logic (no Python-side changes)
- All Python source files
- All test files

---

## 6. Accessibility

- `prefers-reduced-motion: reduce` → all `animation` and `transition` set to `0.001ms` duration
- Contrast ratios: Dark ≥ 4.5:1, Light ≥ 4.5:1, Pastel ≥ 4.8:1 (deep purple on lavender), Catppuccin ≥ 5.2:1
- Focus rings preserved on all interactive elements
- `backdrop-filter` has no a11y impact

---

## 7. Performance Constraints

- No JS framework — vanilla JS only (IntersectionObserver, requestAnimationFrame)
- `will-change: transform` applied only to aurora orbs (4 elements, `position:fixed`)
- Chart.js already bundled — animation config is zero-cost addition
- All CSS animations GPU-composited (transform + opacity only — no layout-triggering props)
- Skeleton screens prevent layout shift (CLS)
