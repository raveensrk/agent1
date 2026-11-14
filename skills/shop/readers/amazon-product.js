// Run on any amazon.in page after the pincode is set. Edit IDS first.
// Fetches each product page with the session's pincode; no navigation.
const IDS = ['ASIN1', 'ASIN2'];
const out = [];
for (const id of IDS) {
  const h = await (await fetch('/dp/' + id, { credentials: 'include' })).text();
  const d = new DOMParser().parseFromString(h, 'text/html');
  const q = (s) => d.querySelector(s)?.textContent.replace(/\s+/g, ' ').trim();
  const specs = [...d.querySelectorAll('#feature-bullets li')]
    .map((e) => e.textContent.replace(/\s+/g, ' ').trim()).join(' | ');
  out.push({
    url: 'https://www.amazon.in/dp/' + id,
    title: q('#productTitle'),
    price: q('.priceToPay .a-offscreen') ||
      q('#corePrice_feature_div .a-offscreen') || q('.priceToPay'),
    rating: q('#acrPopover .a-icon-alt'),
    count: q('#acrCustomerReviewText'),
    delivery: q('#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE'),
    pincode: q('#glow-ingress-line2'),
    offer: q('#itembox-InstantBankDiscount')?.slice(0, 90),
    img: d.querySelector('#landingImage')?.getAttribute('data-old-hires'),
    specs: specs.slice(0, 1500),
  });
}
out;
