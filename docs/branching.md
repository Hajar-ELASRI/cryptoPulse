# Branch and PR convention (proposal)

Short, so the repository stays readable with four people pushing to it.

## Names

`<type>/<area>-<what>` in lower case with hyphens, named after the work, never after a person or a tool.

| Type | Use | Example |
|---|---|---|
| `feature/` | new behaviour | `feature/spark-silver-trades`, `feature/api-live-endpoint` |
| `fix/` | bug fix | `fix/ingestion-kafka-permissions` |
| `docs/` | documentation only | `docs/spark-output-contracts` |

Areas: `ingestion`, `spark`, `api`, `dashboard`, `infra`.

## Rules

- Branch from the integration branch. There is no `develop` or `main` yet; until the team creates them (the coordinator's decision), open PRs against `codex/person-a-ingestion`.
- One topic per branch and per PR. Several small PRs beat one large one.
- Never push to someone else's branch. Ask them, or open a PR into it.
- A stacked PR (built on an unmerged PR) uses that PR's branch as its base and says so in its description. Merge from the bottom up and retarget the next PR when the one below merges. Do not rename or delete a branch while another PR is based on it: GitHub closes the dependent PR.
- Delete a branch after its PR merges.
- Commit messages start with `feat:`, `fix:` or `docs:`.
- PR description: what changed, how to run it, what was checked, what was not.

## Current branches

| Branch | Owner | State |
|---|---|---|
| `codex/person-a-ingestion` | Hajar | ingestion base. The name predates this convention; renaming is Hajar's call and must wait until no PR is based on it. |
| `docs/spark-output-contracts` | Ali | PR 1 |
| `feature/spark-silver-trades` | Ali | PR 2 |
| `feature/spark-gold-indicators` | Ali | PR 3, based on PR 2 |
| `feature/spark-editorial` | Ali | PR 4, based on PR 3 |
