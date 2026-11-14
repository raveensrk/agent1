// Run on a Flipkart search page. Returns rated, buyable results.
// Colour variants share name, rating and count: kept once.
const seen = new Set();
[...document.querySelectorAll('a[href*="/p/itm"]')].map((a) => {
  let c = a;
  for (let i = 0; i < 6 && c.parentElement && c.innerText.length < 80; i++) {
    c = c.parentElement;
  }
  const card = c.innerText.replace(/\n+/g, ' | ');
  const m = card.match(/\| ([\d.]+)\(([\d,]+)\) \| (₹[\d,]+)/);
  if (!m || /Coming Soon|Sold Out|Currently unavailable/i.test(card)) {
    return null;
  }
  const name = card.replace(/^(Sponsored|Ad) \| /, '').split(' | ')[0];
  const key = name + m[1] + m[2];
  if (seen.has(key)) return null;
  seen.add(key);
  return {
    store: 'Flipkart',
    url: a.href.split('?')[0],
    name,
    rating: parseFloat(m[1]),
    count: m[2],
    price: m[3],
    img: c.querySelector('img')?.src,
  };
}).filter(Boolean);
