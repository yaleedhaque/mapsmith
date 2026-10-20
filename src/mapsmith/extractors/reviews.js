// mapsmith — reviews extractor
// Open the Reviews tab of an open place page, load many reviews, extract them.
// Returns { count, cards: [{ author, stars, date, text }] }.
return (async () => {
  const findTab = () => [...document.querySelectorAll('[role="tab"], button, a')]
    .find((e) => /^Reviews$/i.test((e.getAttribute('aria-label') || '').trim())
      || /^Reviews$/i.test((e.textContent || '').trim()));
  const tab = findTab();
  if (tab) { tab.click(); await new Promise((r) => setTimeout(r, 1800)); }

  const sc = [...document.querySelectorAll('div.m6QErb')].find((e) => e.scrollHeight > e.clientHeight + 80)
    || document.querySelector('div[role="feed"]') || document.querySelector('div.m6QErb');
  let last = 0, stable = 0;
  for (let i = 0; i < 30 && stable < 5; i++) {
    if (!sc) break;
    sc.scrollTop = sc.scrollHeight;
    await new Promise((r) => setTimeout(r, 800));
    const n = document.querySelectorAll('.jftiEf').length;
    if (n === last) stable++; else stable = 0;
    last = n;
  }

  const cards = [...document.querySelectorAll('.jftiEf')].map((c) => {
    const q = (s) => { const e = c.querySelector(s); return e ? (e.getAttribute('aria-label') || e.textContent || '').trim() : null; };
    return {
      author: (c.querySelector('.d4r55') || {}).textContent || null,
      stars: q('[aria-label^="Rated"],[aria-label*="star"],[role="img"]'),
      date: (c.querySelector('.rsqaWe') || {}).textContent || null,
      text: (c.querySelector('.wiI7pd') || {}).textContent || null,
    };
  }).filter((r) => r && (r.text || r.stars));

  return { count: cards.length, cards: cards };
})();
