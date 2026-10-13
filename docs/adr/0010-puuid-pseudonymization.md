# ADR-0010 — Pseudonymize `puuid` with HMAC at the harmonized boundary

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

`puuid` is a stable, account-level player identifier. It is structurally necessary: the only
way to list a player's matches is `match-v5/matches/by-puuid/{puuid}/ids`. It is also personal
data — pseudonymous, but re-identifiable by anyone with access to Riot's account API.

Riot's developer documentation treats `puuid` as an internal identifier and directs
applications to display Riot IDs instead, and for VALORANT it requires explicit player opt-in
via Riot Sign-On before personal data is shared. The full Developer Policy text sits behind
authentication on the developer portal and must be read there before anything is published.

Under Brazilian LGPD, a pseudonymous but re-identifiable identifier is personal data, and data
minimization applies to each processing layer independently.

## Decision

Pseudonymize at the boundary between raw and conformed data.

| Layer | `puuid` |
|---|---|
| landing, bronze | present exactly as received — private workspace, needed to crawl |
| harmonized | replaced by `player_sk = HMAC-SHA256(puuid, salt)`; the raw value does not cross |
| consumption | no player-grain output is published; aggregates only |

The salt is stored in the Databricks secret scope as `mls/pseudonym_salt`. Conversion lives in
exactly one module, `src/mls/common/pseudonymize.py`, with unit tests asserting that the same
input always yields the same output and that the salt never appears in a log line.

## Alternatives considered

**Plain `SHA-256(puuid)`.** Rejected: the identifier space is enumerable by anyone who can
call the Riot API, so an unsalted hash is reversible by brute force. It provides the appearance
of protection rather than protection.

**Keep `puuid` in clear text in the harmonized layer, since the workspace is private.**
Rejected: it makes every future export a manual judgement call, and the one time the
judgement is wrong, personal data is published irrevocably. Pseudonymizing at the boundary
makes the safe outcome structural rather than remembered.

**No player-grain table at all.** The most conservative option. Rejected: it removes ladder
composition over time and distinct-player counts, which are legitimate analyses, and
`player_sk` already provides everything they need.

**Tokenization with a reversible lookup table.** Rejected: a reversible mapping is a
re-identification key stored next to the data, which is worse than either alternative, and
nothing in the analytical question requires reversibility.

## Consequences

- Joining a player across matches and across ladder snapshots works, because the pseudonym is
  stable.
- Rotating the salt invalidates every historical `player_sk` and breaks longitudinal joins.
  The salt is therefore treated as permanent project state, and this is stated in the runbook.
- Re-identification from published output is not possible without the salt.
- Reading Riot's Developer Policy while authenticated is a blocking item in the definition of
  done for any publication task.
- A schema contract test will assert that published output contains no player identifier
  column, failing the build if one is introduced. That test is deferred with the public
  showcase.
