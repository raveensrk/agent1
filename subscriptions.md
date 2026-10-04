# Subscriptions

Split from [common.md](common.md); routed by [rules_context.ts](harness/extensions/rules_context.ts).

On this machine, a request for what subscriptions I have starts with two reads:

1. `~/repos/ledger/journals/transactions.ledger`
2. `~/Library/Mail/V10/MailData/Envelope Index`

Then open `https://apps.apple.com/account/subscriptions` for Apple subscriptions. Do not start at System Settings, StoreKit, or Chrome commerce databases.

The keep list is `~/repos/ledger/data/subscriptions.json`. A subscription not in `current` must be unsubscribed.
