// mapsmith — detail extractor
// Runs on an open Google Maps *place* page. Returns a JSON object with identity,
// contact, hours, photos (Google-profile avatars removed), menu link, order-online
// links, a best-effort price band and popular items.
//
// Optional Bangla-name and ৳/person fields are captured when present on the page;
// SQLite/CSV columns are created for them but left null elsewhere.
return (async () => {
  const main = document.querySelector('div[role="main"]');
  const txt = main ? main.innerText : '';
  const el = (s) => document.querySelector(s);
  const label = (s) => {
    const e = el(s);
    return e ? (e.getAttribute('aria-label') || '').trim() : null;
  };
  const strip = (s, p) => (s && s.startsWith(p)) ? s.slice(p.length).trim() : s;

  const hours = [...document.querySelectorAll('[aria-label]')]
    .map((e) => e.getAttribute('aria-label'))
    .filter((a) => a && /^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),/.test(a));

  // Real place photos only. Google mixes reviewer avatars (/a/, /a-) and the
  // generic account placeholder (/ogw/) into the page — never the place's own photo.
  const AVATAR = /googleusercontent\.com\/(a|a-|ogw)\//;
  const best = {};
  [...document.querySelectorAll('img')].forEach((i) => {
    const u = i.src || '';
    if (!u.includes('googleusercontent') || AVATAR.test(u)) return;
    const base = u.split('=')[0];
    const size = +((u.match(/=w(\d+)/) || [])[1] || 0);
    if (!best[base] || size > best[base]) best[base] = size;
  });
  const photos = Object.keys(best).map((b) => b + '=w1080-h1080-k-no');

  const lines = txt.split('\n').map((s) => s.trim()).filter(Boolean);
  const service = lines.filter((l) =>
    /^(Dine-in|Takeaway|Delivery|No-contact delivery|Drive-through|Kerbside pickup|Dine-in|Takeout|Outdoor seating)$/.test(l));

  const CATW = /\b(restaurant|cafe|café|coffee shop|coffee|tea house|tea stall|tea shop|bakery|sweet shop|sweets|dessert|ice cream|fast food|food court|food truck|food cart|street food|snack|canteen|buffet|biryani|chinese|indian|thai|japanese|korean|pizza|burger|seafood|barbecue|bbq|grill|juice|bar|lounge|beverage|dairy|halal|noodle|kebab|shawarma|diner|bistro|eatery|hotel|confectionery|fuchka|pitha|supermarket|grocery|pharmacy|clinic|salon|gym|bank|atm|school|college|hospital|hotel|store|shop|market|bazaar|fashion|clothing|electronics|mobile|hardware|furniture|boutique|tailor|laundry|travel|agency|petrol|fuel|gas|car|auto|service)\b/i;
  let category = null;
  const h1 = (el('h1') || {}).textContent || '';
  for (const e of document.querySelectorAll('button, div, span, a')) {
    if (e.children.length > 0) continue;
    const t = (e.textContent || '').trim();
    if (t.length > 2 && t.length < 32 && CATW.test(t) && !/\d/.test(t) && !t.includes(h1)
        && !/popular|review|menu|photo|direction|save|share|overview|claim/i.test(t)) { category = t; break; }
  }

  const rc = txt.match(/\n\(([\d,]+)\)/) || txt.match(/[^\d]\(([\d,]{2,})\)/);
  const review_count = rc ? +rc[1].replace(/,/g, '') : null;
  const rt = txt.match(/\n([0-5]\.\d)\n/);
  const rating = rt ? +rt[1] : null;

  const ORDER_RE = /foodpanda\.|pathao\.com|ubereats|sheba\.xyz|hungrynaki|zomato|deliveroo|justeat|doordash|grubhub|swiggy|zomato\.com|talabat|glovo|wolt|opentable|quandoo|thefork/i;
  const order = [];
  {
    const seen = new Set();
    for (const a of document.querySelectorAll('a[href]')) {
      const href = a.href;
      if (!ORDER_RE.test(href)) continue;
      const host = (href.split('/')[2] || '').replace(/^www\./, '');
      if (seen.has(host)) continue;
      seen.add(host);
      order.push({ label: (a.getAttribute('aria-label') || a.textContent || host).trim().slice(0, 40), url: href });
      if (order.length >= 6) break;
    }
  }

  const priceLevel = (txt.match(/(?:^|\n)\s*(৳{1,4}|€{1,4}|\${1,4}|£{1,4})\s*(?:\n|$)/) || [null])[0];
  const pricePerPerson = (txt.match(/(?:৳|€|\$|£)[\d,]+[–-][\d,]+ per person/) || [null])[0];

  const popular = [];
  {
    const seen = new Set();
    const priceEls = [...document.querySelectorAll('*')]
      .filter((e) => e.children.length === 0 && /^\s*(৳|€|\$|£)\s?[\d,]+/.test(e.textContent || ''));
    for (const pe of priceEls) {
      const cont = pe.closest && (pe.closest('li') || pe.closest('[jsaction]') || pe.parentElement?.parentElement?.parentElement);
      let nm = null;
      if (cont) {
        nm = [...cont.querySelectorAll('*')]
          .map((x) => (x.children.length === 0 ? (x.textContent || '').trim() : ''))
          .find((t) => t && t.length > 1 && t.length < 44 && !/^[৳€£$]/.test(t)
            && !CATW.test(t) && !/^\d|popular|price|per person/i.test(t)) || null;
      }
      const price = (pe.textContent || '').trim();
      if (nm && !seen.has(nm)) { seen.add(nm); popular.push({ name: nm, price }); }
      if (popular.length >= 12) break;
    }
  }

  const bn = lines.slice(0, 4).find((l) => /[\u0980-\u09FF]/.test(l)) || null;
  const menuUrl = (el('a[data-item-id="menu"]') || {}).href || null;

  return {
    name: h1 || null,
    category: category,
    price_level: priceLevel,
    popular_items: popular,
    rating: rating,
    review_count: review_count,
    order_online: order,
    menu_url: menuUrl,
    name_local: bn,
    address: strip(label('button[data-item-id="address"]'), 'Address:'),
    phone: strip(label('button[data-item-id^="phone"]'), 'Phone:'),
    website: (el('a[data-item-id="authority"]') || {}).href || null,
    plus_code: strip(label('button[data-item-id="oloc"]'), 'Plus code:'),
    located_in: (label('[data-item-id="locatedin"]') || '').replace('Located in:', '').trim() || null,
    hours: hours,
    service_options: service,
    price_per_person: pricePerPerson,
    photo_count: photos.length,
    photos: photos,
  };
})();
