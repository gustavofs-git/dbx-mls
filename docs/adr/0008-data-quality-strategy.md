# ADR-0008 — Drop impossible values, keep valid-but-out-of-scope records

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

Records arriving from the Riot API fall into categories that look similar and are not:

| Example | Nature |
|---|---|
| `kills = -1` | physically impossible — an API or parsing defect |
| `champion_name IS NULL` | a required field is absent — a defect |
| a match lasting 147 seconds (a remake) | **true**: the match happened and ended that way |
| `queueId = 450` (ARAM) | **true**: a real match, outside the analytical question |

Treating all four the same way produces one of two failures. Keeping everything lets a `-1`
reach an average in the consumption layer, so published win rates are wrong. Dropping
everything deletes true information — and with it the ability to answer "what share of
Challenger matches are remakes?", which is itself an interesting measurement.

## Decision

Separate **data quality** from **business scope**, and place them in different layers.

**At the bronze → harmonized boundary — data quality.** Expectations drop records whose
values cannot exist, and every drop is counted into `ops.dq_metrics`.

```python
@dlt.expect_all_or_drop({
    "valid_champion": "champion_name IS NOT NULL",
    "sane_kills":     "kills >= 0",
    "sane_deaths":    "deaths >= 0",
    "valid_team":     "team_id IN (100, 200)",
})
```

A structural invariant — a match must have exactly ten participants — fails the pipeline
instead, because a violation means the parsing is wrong, not the data.

**In the harmonized layer — attributes, not filters.** `is_remake`, `queue_id`, `game_mode`
and `ended_in_early_surrender` are stored as columns. Nothing true is removed.

**In the consumption layer — business scope.** The four fact views apply the analytical
filter, once:

```sql
CREATE OR REPLACE VIEW mls.consumption.fct_match_participant AS
SELECT p.* FROM mls.harmonized.match_participants p
JOIN mls.harmonized.matches m USING (match_id)
WHERE NOT m.is_remake AND m.queue_id = 420;
```

There is **no quarantine table.** Dropped records remain in bronze in their original form, so
nothing is lost; what the drop removes is the risk of corruption propagating.

## Alternatives considered

**A quarantine table holding rejected rows with a reason.** The pattern most reference
architectures recommend, and genuinely useful at scale when someone is accountable for
remediating rejects. Rejected here on the project owner's decision: bronze already retains
every rejected record in its original form, so a quarantine table is a second copy of data
that is already queryable, and the drop *counts* in `ops.dq_metrics` provide the signal that
the table would otherwise carry. The cost accepted is that inspecting a specific rejected
record means querying bronze rather than a convenient table.

**Validity flags instead of drops — `is_valid` plus `validation_flags`, nothing removed.**
Rejected: the owner's position is that corrupt data should be cleaned, and flags do not clean
it — they relocate the obligation to every downstream query, where one forgotten
`WHERE is_valid` silently reintroduces the defect.

**Drop remakes and non-ranked queues at the harmonized layer too.** Simpler, and produces an
identical result today. Rejected because the analytical scope is the thing most likely to
change: answering "include ARAM" would require reprocessing from bronze instead of editing a
view, and the harmonized layer would stop being a faithful picture of what happened and
become a picture with an opinion already applied.

**Great Expectations or Soda.** See [ADR-0009](0009-native-expectations-over-external-dq.md).

## Consequences

- Published aggregates cannot be corrupted by impossible values.
- The harmonized layer remains a complete and faithful record of the sampled universe, so
  remake rate, queue mix and game-mode distribution are all measurable.
- Changing analytical scope is an edit to four view definitions, reviewable in a pull request.
- `ops.dq_metrics` records a drop rate per rule per run, which is the input to the data
  quality dashboard and makes silent data loss impossible.
- Inspecting an individual rejected record requires a bronze query with `VARIANT` navigation.
  This is a deliberate trade and is documented in the runbook.
