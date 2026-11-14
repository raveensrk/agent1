---
name: shop
metadata:
  scope: global
description: Find a product across Indian online stores and list the top 5 (more on request) best to worst by review-weighted rating, each with a picture, every store's price and link, offers, delivery date to the user's pincode, and one pro and one con. Asks for product details first and remembers the pincode. Lists only - never adds to cart or buys. Use when the user says shop for, find me, compare prices for, best rated, which one should I buy, search Amazon or Flipkart, or runs /shop.
argument-hint: "[product to find]"
---

# Shop

Find a product, rank it by rating, show pictures and links.
The user buys. This skill never adds to a cart, never checks out.

## 1. Location

Read the pincode from `~/.config/shop/config`, a line `pincode=560001`.

- File missing or no pincode: ask for the 6-digit pincode, then write the
  file. Create `~/.config/shop/` if needed.
- Pincode present: say it in one line, "Delivering to 560001". The user may
  give a new one; save it.
- Never write the pincode into a repo, a URL query string or the reply beyond
  that one line.

## 2. Product details

Start from the argument. Ask only what it does not already say. A number in
the request, e.g. "top 10 earbuds", sets the list size.
Ask in one round, at most four questions, with the harness's question tool
when it has one (Claude Code: `AskUserQuestion`).

- Budget: min and max in rupees.
- Brand: preferred, or excluded.
- Key specs: questions that fit the product. Laptop: RAM, storage, screen.
  Shoes: size, colour, use. Phone: storage, 5G, camera.
- Delivery by: a date, or "no rush".

Offer "No preference" on each. Repeat the answers back in one line each.

## 3. Pick stores

Always Amazon.in and Flipkart. Add stores by category:

| Category               | Extra stores                       |
| ---------------------- | ---------------------------------- |
| Clothes, shoes, beauty | Myntra, Ajio, Meesho               |
| Electronics, appliance | Croma, Reliance Digital, Tata Cliq |
| Anything else          | none                               |

Search start points. Encode the query; if a URL fails, use the site's own
search box.

- Amazon.in: `https://www.amazon.in/s?k=QUERY`
- Flipkart: `https://www.flipkart.com/search?q=QUERY`
- Myntra: `https://www.myntra.com/QUERY`
- Ajio: `https://www.ajio.com/search/?text=QUERY`
- Meesho: `https://www.meesho.com/search?q=QUERY`
- Croma: `https://www.croma.com/searchB?q=QUERY%3Arelevance&text=QUERY`
- Reliance Digital: `https://www.reliancedigital.in/products?q=QUERY`
- Tata Cliq: `https://www.tatacliq.com/search/?searchCategory=all&text=QUERY`

## 4. Search in the browser

Use the harness's browser, not a scraper and not web search: live pages show
live prices and stock.

- Claude Code: the built-in browser pane; Claude in Chrome if the user asks.
  Read pages as text or the accessibility tree; screenshot only when text
  fails.
- pi: its browser or computer-use tool.

Saved page readers in [readers/](readers/) do the reading in one step each.
Read the file, then run its code in the page with the browser's JavaScript
tool (Claude Code: `javascript_tool`). No JavaScript tool: read the page as
text instead.

- [amazon-search.js](readers/amazon-search.js): Amazon.in search results.
- [amazon-product.js](readers/amazon-product.js): many Amazon.in product
  pages at once; set `IDS` first.
- [amazon-reviews.js](readers/amazon-reviews.js): reviews on an open Amazon.in
  product page.
- [flipkart-search.js](readers/flipkart-search.js): Flipkart search cards.
- [flipkart-product.js](readers/flipkart-product.js): many Flipkart product
  pages and their reviews at once; set `PATHS` first.

A reader returns nothing or wrong fields: the site changed. Read the page as
text, finish the run, and say in the reply which reader needs fixing.

On each store:

1. Open the search URL. Apply the budget with the site's price filter when
   it has one.
2. Read the first page of results. For each item take: name, brand, model or
   variant, price, star rating, rating count, product URL, image URL.
3. Drop items marked Sponsored, Ad or Promoted.
4. Drop items outside budget, excluded brands, or clearly missing a
   required spec.
5. Drop items with no rating.

Stop on a store, skip it and say so in the reply, when it shows a sign-in
wall, a CAPTCHA or a bot check. Never solve a CAPTCHA. Never sign in.

## 5. Merge duplicates

Same brand, same model, same variant (size, colour, storage) on two stores is
one product. Keep each store's price and link, cheapest first.
Its rating is the count-weighted mean of the stores' ratings; its count is the
sum.

## 6. Rank

Weighted rating, so few reviews cannot beat many:

```
score = (v * R + m * C) / (v + m)
```

- `R`: the product's star rating. `v`: its rating count.
- `C`: mean rating of all candidates. `m`: 100.

Sort by score, best first. Keep the top 5. The user may ask for more, e.g.
"top 10" or "show 15": keep that many.

Fewer match than wanted: show what matched. Say why the list is short in one
line. Never pad it with items that fail a filter.

## 7. Fill in the kept items

Open each kept product page, one store per product is enough, the cheapest.

- Delivery: enter the pincode in the page's delivery check field. Read the
  date. Drop the item if it misses the user's delivery-by date; refill from
  the next ranked item.
- Offers: bank and card offers shown on the page, at most two, short.
- Pro and con: one line each from real buyer reviews, in your own words.
  Read the reviews page or section, not the store's summary. No reviews
  readable: write "not shown".
- Picture: the main product image URL, full `https://`.

Read only. Never click Buy, Add to cart or a wishlist button.

Store notes, learned on real runs:

- Amazon.in: set the pincode once in the "Delivering to" dialog; later
  `/dp/ASIN` pages show delivery for it. "Customers say" is often about the
  brand, not the product: use the reviews from `amazon-reviews.js`.
- Flipkart: set the pincode once in "Select delivery location", pick the
  match, then Confirm. No sign-in needed. Specs sit behind the
  Specifications tab; reviews are at the product URL with `/p/` changed to
  `/product-reviews/`. The first `₹` on a product page may belong to another
  item: take the price from the search card.
- Reliance Digital: search cards show no rating; use it for price only.
- Check each required spec on the product page, not only in the title.
  Page shows it fails a spec, e.g. 20 h battery for "30+ h": drop it.
  Page does not mention the spec at all: keep it, put ⚠ after the name, and
  say in the row which spec is not confirmed.

## 8. Reply

Markdown. One block per product, ranked. No table: images break tables.

```
### 1. Brand Model Variant

![Brand Model](https://image-url)
Picture: https://image-url

★ 4.6 (8,214 ratings) · score 4.58

- ₹1,299 - [Flipkart](https://www.flipkart.com/...)
- ₹1,349 - [Amazon.in](https://www.amazon.in/...)

Delivery: Tue 18 Nov to 560001
Offers: 10% off HDFC cards
Pro: battery lasts two days. Con: charger not in box.
```

- The `Picture:` line is the fallback where images do not render.
- Links go to the product page, never to search results. Strip tracking
  query parameters when the page still loads without them.
- Prices and ratings exact, as the page showed them.
- End with: stores searched, stores skipped and why, items dropped for a
  spec or delivery, why the list is short if it is, readers that failed, and
  the search time.

## Rules

- List only. No cart, no checkout, no wishlist, no sign-in.
- Never enter payment, card or login details.
- Prices change. Say the list is as of now.
- Never invent a rating, price, date or image. Missing on the page: write
  "not shown".
