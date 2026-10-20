// mapsmith — list extractor
// Scrolls the Google Maps results feed until it stops growing, then extracts the
// result cards. Returns { count, cards: [{ name, lat, lng, ftid, url, lines }] }.
//
// `ftid` is the Google CID pair extracted from the place href
// (the `0x...:0x...` token) — stable across queries, so it is the dedupe key.
return (async () => {
  const feed = document.querySelector('div[role="feed"]');
  if (feed) {
    let last = -1, stable = 0;
    for (let i = 0; i < 25 && stable < 4; i++) {
      feed.scrollTop = feed.scrollHeight;
      await new Promise((r) => setTimeout(r, 700));
      const n = document.querySelectorAll('a.hfpxzc').length;
      if (n === last) stable++; else stable = 0;
      last = n;
    }
  }
  const cards = [...document.querySelectorAll('div.Nv2PK')].map((c) => {
    const a = c.querySelector('a.hfpxzc');
    if (!a) return null;
    const href = a.href;
    const m = href.match(/!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/);
    const pid = href.match(/!1s(0x[0-9a-f]+:0x[0-9a-f]+)/);
    const map = (c.innerText || '').split('\n').map((s) => s.trim()).filter(Boolean);
    return {
      name: a.getAttribute('aria-label'),
      lat: m ? +m[1] : null,
      lng: m ? +m[2] : null,
      ftid: pid ? pid[1] : null,
      url: href,
      lines: map,
    };
  }).filter((c) => c && c.ftid);
  return { count: cards.length, cards: cards };
})();
