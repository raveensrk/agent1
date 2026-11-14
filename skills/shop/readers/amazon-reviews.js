// Run on an open Amazon.in product page. Scrolls to load reviews.
// Reviews are read from page text: their boxes are often empty.
window.scrollTo(0, document.body.scrollHeight * 0.7);
await new Promise((r) => setTimeout(r, 2500));
const t = document.body.innerText;
const i = t.indexOf('Customers say');
const j = t.search(/Top reviews from India|Top reviews/);
const end = t.search(/See more reviews|Top reviews from other countries/);
const block = j < 0 ? '' : t.slice(j, end > j ? end : j + 6000);
({
  summary: i < 0 ? '' : t.slice(i + 14, i + 500),
  reviews: block.split(/\n(?=\d(?:\.\d)? out of 5 stars\n)/)
    .slice(1, 9).map((r) => r.replace(/\s+/g, ' ').trim().slice(0, 400)),
});
