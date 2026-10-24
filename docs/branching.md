# Branch and PR convention

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

- `main` is the integration branch and holds the complete app. Branch from `main` and open PRs against `main`; review by another member before merging.
- One topic per branch and per PR. Several small PRs beat one large one.
- Never push to someone else's branch. Ask them, or open a PR into it.
- A stacked PR (built on an unmerged PR) uses that PR's branch as its base and says so in its description. Merge from the bottom up and retarget the next PR when the one below merges. Do not rename or delete a branch while another PR is based on it: GitHub closes the dependent PR.
- Delete a branch after its PR merges.
- Commit messages start with `feat:`, `fix:` or `docs:`.
- PR description: what changed, how to run it, what was checked, what was not.

## Branches at the creation of `main`

`main` was created from `codex/person-a-ingestion` and received, by merge commits, the four Spark branches and the two documentation branches. Nothing was deleted; the branches below stay as history and can be removed by their owner once no open PR is based on them.

| Branch | Owner | Content |
|---|---|---|
| `main` | team | everything below, the complete app |
| `codex/person-a-ingestion` | Hajar | ingestion and infrastructure (name predates the convention) |
| `docs/spark-output-contracts` | Ali | Spark output contracts |
| `feature/spark-silver-trades` | Ali | Silver trades job |
| `feature/spark-gold-indicators` | Ali | Gold indicators, alerts, replay |
| `feature/spark-editorial` | Ali | news, social posts, sentiment |
| `docs/branch-convention` | Ali | this document |
