# NightWatcher Mobile & Responsive Checklist

This checklist verifies all layout and viewport behaviors in accordance with Phase A (Items 1, 3, 16, and layout part of 20).

---

## 1. Viewport Matrix

| Viewport Category | Screen Width (CSS px) | Target Devices | Layout Behavior | Horizontal Scroll? | Overflow / Clipping? | Touch Targets | Status |
| :--- | :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| **Small Phone** | **320px – 360px** | iPhone SE, Galaxy A-series | 1-column stacked, mobile hamburger navigation, metrics grid 2-col, full-width actions. | None (`overflow-x: hidden`) | None (modal max 90vh, scrollable) | >= 44px | **PASS** |
| **Standard Phone** | **375px – 414px** | iPhone 13/14/15, Pixel 7/8 | 1-column stacked, touch-scroll tabs, readable badges, safe area insets. | None | None | >= 44px | **PASS** |
| **Large / Phablet** | **428px – 600px** | Pro Max, Galaxy Plus | Fluid cards, touch-scroll simulator buttons, comfortable padding. | None | None | >= 44px | **PASS** |
| **Tablet Portrait** | **600px – 768px** | iPad Mini, Galaxy Tab A | 2-column metrics, drawer/hamburger nav, scrollable blocklist table. | None | None | >= 44px | **PASS** |
| **Tablet Landscape** | **768px – 992px** | iPad 10th gen, iPad Air | Inline tab bar, responsive grid cards, expanded side-by-side feeds. | None | None | >= 44px | **PASS** |
| **Desktop / Laptop** | **1200px+** | Standard monitors, MacBooks | 4-column metrics, full horizontal layout, max-width 1380px container. | None | None | Normal | **PASS** |

---

## 2. Insets and Component Overflow Audit

- [x] **No Unintended Horizontal Scroll:** Root container enforces `html, body { overflow-x: hidden; width: 100%; }`.
- [x] **Mobile Hamburger Drawer:** Added `#mobile-nav-drawer` (< 768px) with accessible toggle button, overlay, and keyboard dismiss (`Escape`).
- [x] **Detail Modal Height:** `#alert-modal .modal-window` capped at `max-height: 90vh`, with `.modal-body` scrollable to prevent off-screen clipping.
- [x] **Touch Targets:** All primary buttons and hamburger triggers sized to >= 44px x 44px.
- [x] **Orientation Changes:** Flex and grid layouts adjust fluidly between portrait and landscape without loss of state.
