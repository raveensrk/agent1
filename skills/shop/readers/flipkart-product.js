// Run on any flipkart.com page after the pincode is set. Edit PATHS first:
// product paths like /name/p/itmXXXX. Fetches page and reviews; no clicks.
const PATHS = ['/name/p/itmXXXX'];
const text = (h) => {
  const d = new DOMParser().parseFromString(h, 'text/html');
  d.querySelectorAll('script,style').forEach((e) => e.remove());
  return d.body.textContent.replace(/\s+/g, ' ');
};
const out = [];
for (const p of PATHS) {
  const h = await (await fetch(p)).text();
  const t = text(h);
  const r = text(await (await fetch(p.replace('/p/', '/product-reviews/'))).text());
  const spec = t.slice(t.indexOf('Specifications'), t.indexOf('Specifications') + 2500);
  out.push({
    url: 'https://www.flipkart.com' + p,
    delivery: (t.match(/Delivery by.{0,30}/) || [''])[0],
    offer: (t.match(/Bank offers.{0,80}/) || [''])[0],
    battery: (t.match(/Up to \d+ hr of Battery Life/) || [''])[0],
    img: (h.match(/https:\/\/rukminim2\.flixcart\.com\/image\/\d+\/\d+\/[^"\s]+?\.(jpeg|jpg|png)/) || [''])[0],
    specs: spec,
    reviews: (r.match(/(Verified Purchase|ago)[^]{0,260}/g) || []).slice(0, 8),
  });
}
out;
