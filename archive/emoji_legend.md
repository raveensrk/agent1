# Emoji Legend

Canonical emoji vocabulary for agent reports and summaries, across every project.

## Core legend (11)

### Item status - starts a checklist row or table cell

Answers: what happened to this item?

| Emoji | Meaning |
|-------|---------|
| ✅ | Done / success / verified |
| ❌ | Failed / missing / not done |
| ⚠️ | Warning - done but with caveats, or a non-blocking issue |
| ⏳ | Pending / in progress / waiting on something |
| 📥 | New / incoming / not yet triaged |
| 🗑️ | Dropped / no longer relevant |

### Rollup health - one per project, area, or section heading

Answers: how is this area overall?

| Emoji | Meaning |
|-------|---------|
| 🟢 | On track / healthy |
| 🟡 | Needs attention / at risk |
| 🔴 | Blocked / critical |

### Markers - communication flags

| Emoji | Meaning |
|-------|---------|
| ❓ | Needs the human's input - a decision or answer only they can give |
| 💡 | Idea / suggestion / optional improvement |

## Code-project extension (+2)

For dev repos only:

| Emoji | Meaning |
|-------|---------|
| 🐛 | Bug / defect found |
| 🚀 | Shipped / deployed / released |

## Usage rules

- The emoji starts the line or cell; one status emoji per item.
- Item emojis (✅ ❌ ⚠️ ⏳ 📥 🗑️) mark single items; health emojis (🟢 🟡 🔴) summarize areas - don't mix tiers. ⚠️ flags an item, 🟡 flags an area; ❌ fails an item, 🔴 blocks an area.
- Group ❓ items together (top or bottom of the report) so "what do you need from me" is scannable at a glance.
- A doc may define its own local legend for other purposes; reports and summaries always use the meanings on this page.
