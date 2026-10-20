// mapsmith — menu extractor
// Clicks the "Menu" tab (Google's structured menu) on an open place page, scrolls
// the menu region to lazy-load every item image, and returns the dish/menu photos
// with best-effort captions, plus the menu text (sections + items + prices) and the
// external menu link.
//
// Returns { clicked, menu_url, menu_text, image_count, images:[{url,caption}] }
return (async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const clean = (s) => (s || '').replace(/[\ue561\ue000-\uf8ff]/g, '').replace(/\s+/g, ' ').trim();
  const GENERIC = /^(popular|highlights?|menus?|photos?|see all|view all|all|overview|reviews?|about|by owner|food ?& ?drink|more|add photos ?& ?videos|photo \d+ of \d+|\+ ?\d+.*|\d+\+? ?photos?.*)$/i;

  // 1) click the "Menu" tab if the place has one
  let clicked = false;
  const tabs = [...document.querySelectorAll('button')]
    .filter((b) => (b.getAttribute('jsaction') || '').includes('tabs.tabClick'));
  const menuTab = tabs.find((b) => /^menus?$/i.test((b.getAttribute('aria-label') || b.innerText || '').trim()));
  if (menuTab) { menuTab.click(); clicked = true; await sleep(3500); }

  // 2) scope to the menu region so we do NOT pick up hero/review photos
  const menuLink = (document.querySelector('a[data-item-id="menu"]') || {}).href || null;
  const menuRegion = document.querySelector('[role="region"][aria-label="Menu"]');
  if (!clicked && !menuRegion) {
    return { clicked: false, menu_url: menuLink, menu_text: '', image_count: 0, images: [] };
  }
  const root = menuRegion || document.querySelector('div[role="main"]') || document;

  // 3) scroll the scrollable element inside the menu region so every item lazy-loads
  let sc = null;
  for (const e of root.querySelectorAll('div')) {
    if (e.clientHeight > 150 && e.scrollHeight - e.clientHeight > 150) { sc = e; break; }
  }

  const AVATAR = /googleusercontent\.com\/(a|a-|ogw)\//;
  const seen = new Map(); // base url -> caption
  const grab = () => {
    root.querySelectorAll('img').forEach((img) => {
      const u = img.src || '';
      if (!u.includes('googleusercontent') || AVATAR.test(u)) return;
      const base = u.split('=')[0];
      let cap = clean(img.getAttribute('aria-label') || img.alt || '');
      if (!cap || /^photo \d+ of \d+$/i.test(cap)) {
        cap = '';
        let e = img;
        for (let d = 0; d < 8 && e; d++) {
          e = e.parentElement;
          const t = clean(e && e.innerText);
          if (t && t.length >= 2 && t.length <= 50) { cap = t; break; }
        }
      }
      if (GENERIC.test(cap)) cap = '';
      const prev = seen.get(base);
      if (prev === undefined || (!prev && cap)) seen.set(base, cap.slice(0, 80));
    });
  };
  grab();
  if (sc) {
    for (let i = 0; i < 8; i++) {
      sc.scrollTop = sc.scrollHeight;
      await sleep(900);
      const before = seen.size;
      grab();
      if (seen.size === before && i >= 2) break;
    }
  }

  const txt = clean(root.innerText || '');
  const images = [...seen.entries()].map(([base, caption]) => ({ url: base + '=w1080-h1080-k-no', caption }));
  return { clicked, menu_url: menuLink, menu_text: txt.slice(0, 3000), image_count: images.length, images };
})();
