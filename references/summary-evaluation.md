# Editorial regression checks

The shared policy in `app/summary_policy.txt` applies to extraction, recursive merge and the chat skill. A policy change invalidates the extraction and merge caches; existing library summaries are retained until explicitly regenerated.

For prompt edits, run a real model on a full transcript through `summarize`, not just one isolated sentence. Inspect the merged output using these criteria:

- Does it explain the author's thesis, reasoning and concrete examples, rather than list topics?
- Does the opening overview explain the problem, reasoning and conclusion in a readable paragraph (normally 200–350 Chinese characters for essence), rather than a compressed slogan? Short or simple source material should remain proportional.
- Are disputed claims attributed to the speaker without becoming advice in the assistant's voice?
- Are caveats limited to material issues and consolidated into at most two note sentences?
- Are the speaker's own qualifications preserved, including warnings against reckless action?
- Does merging preserve distinct points instead of accumulating defensive comments?
- Are pure promotional filler and visual-only content still handled honestly?

Representative case: an income-comparison talk argues that salaries adjust slowly and are limited by working hours, uses a tea-shop pricing example, contrasts asset and business income, then recommends using wages as a foundation while building reusable skills. It also makes broad tax comparisons and warns against excessive borrowing. A useful summary explains those mechanisms and the author's practical conclusion; a brief tax-scope note may be appropriate. A response dominated by “unproven / cannot establish / cannot be used” fails. So does a response that presents the claimed tax exemptions as universal facts or deletes the author's warning about debt.

These are review criteria, not a banned-word filter. Context determines whether a limitation is useful; do not delete sentences by string matching.
