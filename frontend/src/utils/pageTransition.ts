/**
 * Shared page transition utility
 * Provides animated transitions between any pages with header scramble,
 * bordered-box crossfade, and neon glow effects.
 */

/* ── Route configuration ── */

export interface RouteConfig {
  title: string;
  description: string;
  color: string;
}

/**
 * Map of route paths to their display config.
 * Dashboard ("/") title is dynamic (includes username), so we use a placeholder.
 */
const ROUTE_CONFIGS: Record<string, RouteConfig> = {
  '/': { title: 'Welcome back!', description: 'Get started by uploading a CSV dataset or submitting a natural language query.', color: 'pink' },
  '/query': { title: 'Query Your Data', description: 'Ask questions about your data in natural language. Our AI will convert your query into SQL and display the results.', color: 'cyan' },
  '/upload': { title: 'Upload Dataset', description: 'Upload a CSV file to make it queryable. Once uploaded, you can ask natural language questions about your data.', color: 'green' },
  '/datasets': { title: 'Datasets', description: 'Browse your uploaded datasets. Click on any dataset to expand and preview its contents.', color: 'orange' },
  '/history': { title: 'Query History', description: 'Browse your past queries and view their results. Click on any query to expand the full details.', color: 'gold' },
};

export function getRouteConfig(path: string): RouteConfig | undefined {
  return ROUTE_CONFIGS[path];
}

/* ── Text scramble ── */

const SCRAMBLE_GLYPHS = '█▓▒░╔╗╚╝║═┤┬┴┼─┐└┘┌';

/**
 * Animate text from startText to endText with a character-by-character
 * scramble/rewriting effect. Returns a cancel function.
 */
export function scrambleText(
  element: HTMLElement,
  startText: string,
  endText: string,
  durationMs: number,
  flash: boolean,
): () => void {
  const maxLen = Math.max(startText.length, endText.length);
  const startTime = performance.now();
  let rafId = 0;

  const timings = Array.from({ length: maxLen }, (_, i) => ({
    scrambleAt: (i / maxLen) * 0.35,
    settleAt: 0.45 + Math.random() * 0.5,
  }));

  function update(): void {
    const progress = Math.min((performance.now() - startTime) / durationMs, 1);
    let html = '';

    for (let i = 0; i < maxLen; i++) {
      const timing = timings[i] ?? { scrambleAt: 0, settleAt: 0.5 };
      const { scrambleAt, settleAt } = timing;
      if (progress >= settleAt) {
        const ch = endText[i] ?? '';
        html += ch === ' ' ? ' ' : ch;
      } else if (progress >= scrambleAt) {
        const glyph = SCRAMBLE_GLYPHS[Math.floor(Math.random() * SCRAMBLE_GLYPHS.length)];
        if (flash && Math.random() > 0.6) {
          html += `<span class="glyph-flash">${glyph}</span>`;
        } else {
          html += glyph;
        }
      } else {
        const ch = startText[i] ?? ' ';
        html += ch === ' ' ? ' ' : ch;
      }
    }

    element.innerHTML = html;

    if (progress < 1) {
      rafId = requestAnimationFrame(update);
    }
  }

  rafId = requestAnimationFrame(update);
  return () => cancelAnimationFrame(rafId);
}

/* ── Header transition (scramble) ── */

interface HeaderOverlayResult {
  overlay: HTMLDivElement;
  cancels: (() => void)[];
}

/**
 * Creates the header transition overlay with text scramble.
 * Reads the current page's h1 and description, clones them into a fixed overlay,
 * then scrambles towards the destination page's text.
 */
export function createHeaderTransition(
  sourceH1: HTMLElement,
  sourceDesc: HTMLElement,
  destConfig: RouteConfig,
): HeaderOverlayResult {
  const h1Rect = sourceH1.getBoundingClientRect();
  const descRect = sourceDesc.getBoundingClientRect();

  const headerOverlay = document.createElement('div');
  headerOverlay.className = 'header-transition-overlay';
  headerOverlay.setAttribute('data-color', destConfig.color);

  const h1Clone = document.createElement('h1');
  h1Clone.textContent = sourceH1.textContent;

  const descClone = document.createElement('p');
  descClone.textContent = sourceDesc.textContent;

  headerOverlay.appendChild(h1Clone);
  headerOverlay.appendChild(descClone);

  // Position over source header
  const overlayWidth = Math.max(h1Rect.width, descRect.width, 400);
  Object.assign(headerOverlay.style, {
    top: `${h1Rect.top}px`,
    left: `${h1Rect.left}px`,
    width: `${overlayWidth}px`,
    height: `${descRect.bottom - h1Rect.top}px`,
  });

  document.body.appendChild(headerOverlay);

  const cancels: (() => void)[] = [];

  // Start scramble + color transition on next frame
  requestAnimationFrame(() => {
    headerOverlay.classList.add('scrambling');
    headerOverlay.classList.add(`color-${destConfig.color}`);

    const cancelTitle = scrambleText(
      h1Clone,
      sourceH1.textContent ?? '',
      destConfig.title,
      400,
      true,
    );
    const cancelDesc = scrambleText(
      descClone,
      sourceDesc.textContent ?? '',
      destConfig.description,
      400,
      false,
    );
    cancels.push(cancelTitle, cancelDesc);

    // Remove scrambling class when done
    setTimeout(() => {
      headerOverlay.classList.remove('scrambling');
    }, 420);
  });

  return { overlay: headerOverlay, cancels };
}

/* ── Bordered-box snapshot ── */

/** CSS properties to copy inline so the clone renders without its original CSS context */
const BOX_STYLE_PROPS: (keyof CSSStyleDeclaration)[] = [
  'background', 'border', 'borderRadius', 'boxShadow',
  'padding', 'color', 'fontFamily', 'fontSize', 'overflow',
];

/**
 * Create a fixed-position clone of a bordered box element.
 * Copies key visual properties as inline styles so it renders
 * correctly even outside its original CSS selector context.
 */
function snapshotBox(el: HTMLElement): HTMLDivElement {
  const rect = el.getBoundingClientRect();
  const computed = window.getComputedStyle(el);

  const clone = document.createElement('div');
  clone.className = 'box-snapshot-overlay';
  // No innerHTML — just a solid opaque box matching the border/background/shadow.
  // Cloning inner content would lose CSS context and show unstyled elements.

  // Copy key visual properties as inline styles
  for (const prop of BOX_STYLE_PROPS) {
    const val = computed[prop];
    if (typeof val === 'string' && val) {
      clone.style.setProperty(
        prop.toString().replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`),
        val,
      );
    }
  }

  Object.assign(clone.style, {
    position: 'fixed',
    zIndex: '100',
    pointerEvents: 'none',
    top: `${rect.top}px`,
    left: `${rect.left}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
    willChange: 'opacity',
    transition: 'opacity 0.35s ease-out',
  });

  return clone;
}

/* ── Full page transition ── */

interface TransitionState {
  isAnimating: boolean;
  boxOverlay: HTMLDivElement | null;
  headerOverlay: HTMLDivElement | null;
  scrambleCancels: (() => void)[];
}

// Global singleton state for active transitions
const state: TransitionState = {
  isAnimating: false,
  boxOverlay: null,
  headerOverlay: null,
  scrambleCancels: [],
};

export function isTransitioning(): boolean {
  return state.isAnimating;
}

/** Clean up any active transition overlays */
export function cleanupTransition(): void {
  state.scrambleCancels.forEach((cancel) => cancel());
  state.scrambleCancels = [];
  if (state.boxOverlay) {
    state.boxOverlay.remove();
    state.boxOverlay = null;
  }
  if (state.headerOverlay) {
    state.headerOverlay.remove();
    state.headerOverlay = null;
  }
  document.body.classList.remove('has-card-overlay');
  state.isAnimating = false;
}

/**
 * Animate a page transition from the current page to a destination route.
 * This handles:
 * 1. Header scramble (h1 + description text rewrite)
 * 2. Bordered-box crossfade (old box fades out, new box fades in)
 * 3. Navigation while overlays are in place
 */
export function animatePageTransition(
  destPath: string,
  navigateFn: (path: string) => void,
  contentEl?: HTMLElement | null,
): void {
  if (state.isAnimating) return;

  const destConfig = getRouteConfig(destPath);
  if (!destConfig) {
    navigateFn(destPath);
    return;
  }

  // Find the current page's h1 and description
  const appContent = contentEl ?? document.querySelector('.app-content');
  if (!appContent) {
    navigateFn(destPath);
    return;
  }

  const currentPage = appContent.querySelector('[class$="-page"]') as HTMLElement | null;
  if (!currentPage) {
    navigateFn(destPath);
    return;
  }

  const h1El = currentPage.querySelector(':scope > h1') as HTMLElement | null;
  const descEl = currentPage.querySelector(':scope > .page-description') as HTMLElement | null;

  if (!h1El || !descEl) {
    navigateFn(destPath);
    return;
  }

  state.isAnimating = true;

  // ── Header transition (scramble) ──
  const headerResult = createHeaderTransition(h1El, descEl, destConfig);
  state.headerOverlay = headerResult.overlay;
  state.scrambleCancels = headerResult.cancels;

  // ── Bordered-box crossfade ──
  // Snapshot the current page's bordered box with inline styles so it
  // renders independently of CSS context, then crossfade with the new page's box.
  const borderedBox = findBorderedBox(currentPage);
  if (borderedBox) {
    const boxClone = snapshotBox(borderedBox);
    document.body.appendChild(boxClone);
    state.boxOverlay = boxClone;
  }

  // Hide the real h1/desc (header overlay is on top showing the scramble)
  h1El.style.opacity = '0';
  h1El.style.transition = 'opacity 0.15s ease-out';
  descEl.style.opacity = '0';
  descEl.style.transition = 'opacity 0.15s ease-out';

  // Navigate quickly — overlays hide the swap
  setTimeout(() => {
    document.body.classList.add('has-card-overlay');
    navigateFn(destPath);

    // Wait one frame for destination page to mount, then dissolve:
    // just fade out the old box snapshot — the new page renders at full
    // opacity underneath, so the dissolve happens naturally as the
    // snapshot becomes transparent.
    requestAnimationFrame(() => {
      if (state.boxOverlay) {
        state.boxOverlay.style.opacity = '0';
      }

      const headerOv = state.headerOverlay;

      const cleanup = (): void => {
        if (state.boxOverlay) {
          state.boxOverlay.remove();
          state.boxOverlay = null;
        }
        if (headerOv) {
          headerOv.remove();
        }
        state.headerOverlay = null;
        state.scrambleCancels = [];
        document.body.classList.remove('has-card-overlay');
        state.isAnimating = false;
      };

      if (state.boxOverlay) {
        const overlay = state.boxOverlay;
        const onFaded = (fe: TransitionEvent): void => {
          if (fe.propertyName !== 'opacity') return;
          overlay.removeEventListener('transitionend', onFaded);
          cleanup();
        };
        overlay.addEventListener('transitionend', onFaded);
      } else {
        setTimeout(cleanup, 400);
      }
    });
  }, 200);
}

/* ── Helpers ── */

/** Selectors for the main bordered content box on each page */
const BORDERED_BOX_SELECTORS = [
  '.quick-actions',      // Dashboard grid
  '.query-input',        // Query page
  '.upload-form',        // Upload page
  '.dataset-list',       // Datasets page
  '.query-history',      // History page
  '.inspector-content',  // Dataset inspector
];

function findBorderedBox(pageEl: HTMLElement): HTMLElement | null {
  for (const sel of BORDERED_BOX_SELECTORS) {
    const el = pageEl.querySelector(sel) as HTMLElement | null;
    if (el) return el;
  }
  return null;
}
