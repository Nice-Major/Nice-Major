# Cross-Company ATS Job Search: Research and Handoff

**Research date:** 2026-11-17
**Status:** Research and design only. No search implementation changes were made for this investigation.

## Goal

Search Greenhouse, Lever, and Ashby by candidate role titles and eligibility preferences without requiring the candidate to choose employer names. Employer board identifiers may be discovered and maintained internally; they must not be required search inputs.

## Findings from official sources

| Provider | Public listing interface | Identifier required | Cross-company directory/search |
|---|---|---|---|
| Greenhouse | `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs` | A board token, normally visible in the hosted board URL | The public API documentation describes a company's board and its jobs; it does not document a company-directory or all-board search endpoint. |
| Lever | `GET https://api.lever.co/v0/postings/{SITE}?mode=json` (EU host also exists) | A site name for each company | Lever documents company-specific sites and explicitly says the API does not provide full-text search across open jobs. |
| Ashby | `GET https://api.ashbyhq.com/posting-api/job-board/{JOB_BOARD_NAME}` | A job-board name for each organization | The public API documents an organization's postings and how to find that organization's board name; it does not document a company-directory endpoint. |

These APIs can return jobs for a board, after which this repository can apply role, remote-location, sponsorship, eligibility, verification, deduplication, and ranking logic. They cannot search every employer by title without first finding each employer's board identifier.

The current [`data/company-boards.json`](../data/company-boards.json) is a small seed catalog: 9 Greenhouse boards, 8 Ashby boards, and no Lever boards. It is not a vendor-published global directory.

## Is there a published company list?

I found no official, complete, downloadable employer roster from Greenhouse, Lever, or Ashby in their public API documentation. This is consistent with the provider APIs requiring a per-company identifier.

There are public projects that attempt automatic discovery rather than publishing an authoritative vendor roster. For example, [`rishilahoti/ashby-job-scraper`](https://github.com/rishilahoti/ashby-job-scraper) describes discovering Ashby and Greenhouse board identifiers through Common Crawl, validating candidates against the live ATS API, and keeping a registry. Its README says it does not use Common Crawl for Lever because Lever's robots.txt blocks CCBot. This is evidence that a self-growing registry is a practical design pattern, not proof of complete coverage or a vendor-supported directory. That project also describes a self-hosted database/server deployment, so its full hosted system is not a drop-in zero-cost solution for this workflow.

## Common Crawl: useful discovery input, not a complete live index

Common Crawl states that its archives and indexes are free to access. Its index site also asks users not to overload the URL index server and points bulk users to other access methods.

On 2026-11-17, a query against the then-listed `CC-MAIN-2026-43` index for Greenhouse-hosted URLs returned candidate job URLs, many with archived HTTP status `301`. The comparable broad Ashby and Lever requests returned `504` and `503`. This one-time test establishes that the index can expose Greenhouse URL candidates; it does **not** establish reliable or complete discovery for any provider. A captured URL may be stale, redirected, malformed, or no longer a live board and must be checked against the provider's current API.

Lever's current [`jobs.lever.co/robots.txt`](https://jobs.lever.co/robots.txt) disallows `CCBot`, while allowing general search indexing. Therefore Common Crawl should not be treated as a dependable or appropriate primary discovery source for Lever. The similar open-source project reaches the same practical conclusion.

## Recommended design

The candidate continues to configure role titles and eligibility filters, not company names. A background discovery stage maintains an internal, automatically growing list of board identifiers; the existing ATS adapters then fetch postings from those boards and apply the candidate's filters.

### Discovery inputs

1. **Greenhouse and Ashby:** periodically extract candidate board slugs from Common Crawl's public URL index, respecting its load guidance. Normalize host/path variants, reject reserved routes and invalid identifiers, and verify each candidate against the provider's live public endpoint before adding it.
2. **Lever:** discover site names from published Lever job URLs already encountered in permitted public feeds/APIs and job links, plus any future independently validated public dataset. Do not rely on Common Crawl for Lever while CCBot is disallowed. There is no official Lever company list or documented all-sites endpoint.
3. Keep the existing curated boards as bootstrap coverage, but do not require new manual employer entries for normal searching.

This approach removes company names from the user's search setup. It cannot guarantee that every employer using an ATS will be found: each discovery source has incomplete coverage, and Lever is the largest discovery gap under the current free/public constraints.

### Fair board rotation

Searching every discovered board on every daily run may exceed the current per-provider cap and the workflow's 15-minute timeout. Use a persistent cursor and deterministic round-robin batches instead of independent random picks:

- Validate a bounded number of newly discovered candidates per run.
- Fetch a bounded batch of previously verified boards per provider, advancing the cursor after each successful run.
- Prioritize newly discovered and recently active boards; avoid retrying known failures every day.
- If randomization is desired, shuffle within each due batch with a reproducible daily seed, while still advancing the cursor so boards are not repeatedly skipped.
- Apply all configured titles and candidate filters after retrieval, then use the existing eligibility, ranking, and duplicate-history logic.

The current daily workflow already caches `output/state/`; a discovered-board registry and per-provider cursors can be stored there. GitHub Actions cache is useful for continuity but is evictable, so discovery must be able to rebuild the registry rather than treating the cache as the only source of truth.

### Expected behavior and limits

- The user selects titles and filters; companies are discovered and rotated internally.
- The implementation searches verified boards, not every employer on the internet.
- Greenhouse/Ashby discovery can be broad but depends on Common Crawl coverage and service availability.
- Lever coverage remains best-effort unless another compliant, sufficiently broad public source of site identifiers is found.
- No paid search API, metered aggregator, or unsupported Google Jobs endpoint is assumed.
- “Exhaustive across every company” cannot be promised with these public per-company APIs and no complete directory. If that is a literal requirement, it conflicts with the zero-cost/no-provider-directory constraints. A broad, automatically maintained, measurable best-effort catalog is the strongest supportable outcome found.

## Proposed implementation phases

1. **Board registry and state:** define normalized board records, verification status, discovery source, last-seen/last-checked timestamps, and per-provider scan cursors.
2. **Discovery prototype:** add bounded, rate-aware Greenhouse/Ashby Common Crawl discovery; verify candidates live before they enter the fetch pool.
3. **Lever discovery:** derive site identifiers from existing public job URLs and evaluate further public catalogs. Record source and coverage so Lever's reach is measurable; do not silently claim all-company coverage.
4. **Rotating search:** search due boards across all target titles, with bounded concurrency, timeout handling, fairness, and existing eligibility/ranking.
5. **Tests and live validation:** test identifier extraction, malformed/stale candidates, provider errors, cursor rotation, duplicate boards, and request caps. A live search should first report per-provider discovered/verified/fetched counts; send an email only if explicitly requested.

## Credit and continuation notes

I cannot inspect the user's Copilot credit meter, and “93%” does not establish whether that is remaining or already consumed. The implementation is a moderate multi-phase change because discovery, persistence, limits, and cross-provider tests are coupled. This turn deliberately stops after documenting the research; it makes no implementation changes.

### Prompt for a new chat

```text
Continue work in Nice-Major/Nice-Major. First read
docs/ATS_BOARD_DISCOVERY_RESEARCH.md and data/company-boards.json.
The research/design is complete; do not repeat it or start by changing code.

Goal: search Greenhouse, Lever, and Ashby by the candidate's configured role
titles and eligibility preferences, with no employer names required from the
candidate. Internal board IDs may be discovered and rotated automatically.
Keep the workflow zero-cost; do not add paid/metered search APIs or claim that
the public ATS APIs expose every employer.

Implement in small phases: (1) a persisted, rebuildable board registry and
fair per-provider cursors, (2) bounded Common Crawl candidate discovery for
Greenhouse/Ashby with live API validation and load-aware retries, (3) best-effort
Lever ID discovery from permitted public job URLs or a validated public list.
Lever's robots.txt disallows CCBot, so do not depend on Common Crawl for Lever.
Keep the existing curated boards, profile filters, eligibility, ranking,
deduplication, and dispatch history behavior. Add focused tests for extraction,
validation, provider failures, rotation/fairness, and request limits.

Before implementation, report whether any new evidence changes the documented
coverage limits. Do not send live email or delete unrelated files. Run tests,
report discovered/verified/fetched counts by ATS, and document any remaining
coverage gaps.
```

## Sources

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html)
- [Lever Postings API](https://github.com/Lever/postings-api)
- [Lever robots.txt](https://jobs.lever.co/robots.txt)
- [Ashby Public Job Posting API](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [Common Crawl index](https://index.commoncrawl.org/)
- [Common Crawl access and archives](https://commoncrawl.org/get-started)
- [Example community discovery implementation](https://github.com/rishilahoti/ashby-job-scraper)
