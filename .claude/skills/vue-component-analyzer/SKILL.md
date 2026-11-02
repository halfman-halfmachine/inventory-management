---
name: vue-component-analyzer
description: Analyzes Vue 3 component structure in client/src and reports performance problems, code-reuse opportunities, and project-convention violations as a prioritized list with file:line references. Use when asked to analyze, audit, or review Vue components or views, find duplicated frontend logic, or suggest Vue performance optimizations. Report only - does not edit files.
---

# Vue Component Analyzer

Produce a **read-only** report on one or more Vue components. Never edit files while running this skill; the user decides which suggestions to apply (delegate those edits to the `vue-expert` agent per the root CLAUDE.md).

## 1. Scope

- If the user names files or a view, analyze those.
- Otherwise analyze `client/src/views/*.vue` and `client/src/components/*.vue`.
- Always read `client/src/composables/*.js` and `client/src/utils/*.js` first, so you can tell whether reusable helpers already exist.

## 2. Gather facts before judging

Run these from the repo root to find candidates quickly, then read the surrounding code to confirm each one. A grep hit alone is never a finding.

Set `SCOPE` to the files in scope (e.g. `SCOPE="client/src/views/Orders.vue"`), or leave the default. Greps report only in-scope files; the one exception is the duplicated-helper grep, which always searches all of `client/src` so the reuse table can name every copy.

```bash
# The --include globs are quoted so zsh (the macOS default shell) doesn't expand them
SCOPE="${SCOPE:-client/src}"
# Index keys in v-for
grep -rnE 'v-for="\(.*, *(index|idx|i)\)' $SCOPE --include='*.vue'
# Locally redefined helpers that may belong in a composable/util (always all of client/src)
grep -rnE 'const (formatMoney|formatDate|formatCurrency|formatNumber|get[A-Za-z]*Class) *=' client/src --include='*.vue'
# Composables called inside functions instead of once in setup() (6+ spaces of indent)
grep -rnE '^[[:space:]]{6,}const \{.*\} = use[A-Z]' $SCOPE --include='*.vue'
# Direct axios use outside api.js
grep -rn "from 'axios'" $SCOPE --include='*.vue'
# Date parsing - only flag hits with no isNaN check nearby (this grep is noisy; confirm by reading)
grep -rn 'new Date(' $SCOPE --include='*.vue'
# Hard-coded currency symbols: a lone $ or ¥ in a string or as element text
grep -rnE "['\"][\$¥]['\"]|>[\$¥]<|[\$¥]\{\{" $SCOPE --include='*.vue'
```

Note each component's template and script length; flag views with a template over ~100 lines or a script over ~150 lines as split candidates (per `client/CLAUDE.md`).

## 3. Checklist

### Performance
- Derived values computed in methods or inline template expressions that run per render (filter/sort/reduce in the template, or a function called inside `v-for`) - should be `computed`.
- The same filter applied repeatedly, e.g. `getOrdersByStatus('X').length` called several times in the template.
- `v-for` keyed by index, or `v-if` and `v-for` on the same element. Before suggesting a replacement key, check in `server/data/*.json` that the field is actually unique within that list (e.g. `sku` repeats inside some order `items`); if not, suggest a composite key like `` `${item.sku}-${idx}` ``.
- Watchers that trigger API calls without debouncing, or that re-fetch when nothing relevant changed.
- Large arrays sorted or mapped in place on every load (`.sort()` mutates the source).
- Timers, listeners, or intervals not cleaned up in `onBeforeUnmount`.
- Charts recalculating geometry outside `computed`.

### Code reuse
- Helpers duplicated across files (formatters, status-to-class maps, date formatting). Name every file that has a copy and propose one shared location (`composables/` for reactive logic, `utils/` for pure functions).
- Repeated markup blocks (stat cards, item-detail dropdowns, loading/error states) that could become a component.
- API calls made with axios directly instead of through `client/src/api.js`.

### Project conventions
Check against the root `CLAUDE.md` and `client/CLAUDE.md`:
- Composition API with `setup()`; no Options API mixed in.
- Unique `v-for` keys (`sku`, `id`, `month`), never index.
- Dates validated with `isNaN(date.getTime())` before use.
- Loading and error states shown for every async load.
- User-visible text goes through `t()`; currency through `utils/currency.js` (not hard-coded `$` or `¥`).
- No emojis in the UI.
- Non-obvious logic has a comment.

## 4. Report format

Output a single report. Order findings by impact, highest first. Keep each finding to 2-4 lines.

```markdown
# Vue Component Analysis - <scope>

**Summary:** <N> findings (<high>/<medium>/<low>). Top recommendation: <one line>.

## High
1. **<Short title>** - `path/File.vue:LINE`
   <What is wrong and why it matters, one or two sentences.>
   **Suggest:** <concrete change, with a short snippet if it helps>

## Medium
...

## Low
...

## Reuse opportunities
| Helper / pattern | Duplicated in | Suggested home |
|---|---|---|

## Looks good
- <1-3 things the code already does well, so the report is balanced>
```

Severity guide:
- **High**: causes wrong output or a visible bug (wrong currency or amounts, an error state that never clears, index keys on a list that reorders, unvalidated dates that can render "Invalid Date").
- **Medium**: wasted work on every render (repeated filters, composables re-created per call), duplication across 3+ files, convention violations users can see (hard-coded currency, untranslated text).
- **Low**: duplication across 2 files, style, split candidates, theoretical issues the current data can't trigger.

Counting: one finding per root cause. List every affected line in that one finding, and merge problems that share a fix (e.g. a helper that is both slow and unvalidated).

Only report what you confirmed in the code. If a category has no findings, say so in one line instead of padding it.
