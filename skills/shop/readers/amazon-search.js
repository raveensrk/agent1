// Run on an Amazon.in search page. Returns rated, non-sponsored results.
[...document.querySelectorAll('div[data-component-type="s-search-result"]')]
  .map((d) => ({
    store: 'Amazon.in',
    url: 'https://www.amazon.in/dp/' + d.dataset.asin,
    sponsored: !!d.querySelector('.puis-sponsored-label-text') ||
      /Sponsored/i.test(d.innerText.slice(0, 200)),
    name: (d.querySelector('h2')?.innerText || '').slice(0, 140),
    price: d.querySelector('.a-price .a-offscreen')?.textContent,
    rating: parseFloat(d.querySelector('.a-icon-alt')?.textContent),
    count: d.querySelector('a[href*="customerReviews"] span')?.textContent,
    img: d.querySelector('img.s-image')?.src,
  }))
  .filter((x) => !x.sponsored && x.rating);
