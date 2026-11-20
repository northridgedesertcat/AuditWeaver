# Documentation Policy

## What Belongs in Git

| Material | Location | Rule |
| --- | --- | --- |
| Project overview and release history | Root `README*.md`, `CHANGELOG.md`, `LICENSE` | Keep discoverable at the repository root. |
| Architecture, API contracts, developer references | `docs/architecture/`, `docs/development/` | Review against code and link to the owning module. |
| Safe operational procedures | `docs/operations/` | Use placeholders, document prerequisites, and flag destructive commands. |
| Evaluation methods and selected evidence | `docs/evaluation/` | Publish reviewed snapshots with provenance and limitations. |
| Diagram sources and useful exports | Topic-local `diagrams/` directories | Keep an editable source when available; avoid duplicate exports. |
| Product screenshots | `docs/assets/screenshots/` | Use sanitized data; no tokens, accounts, or private infrastructure. |
| Superseded but useful shared design history | `docs/archive/` | Label as historical; do not present old plans as current requirements. |
| A module's operational README | Next to that module | Keep one authoritative README; link from the hub rather than copy it. |
| Executable knowledge, prompts, and test fixtures | Their existing `resources/` or service directories | These are application inputs, not general documentation. |

## What Stays Local

The root `document/` directory remains completely ignored. Use these buckets:

```text
document/
  README.md           Local navigation
  plans/              Draft feature plans and migration proposals
  reviews/            Security findings and environment-specific reviews
  personal/           Career, interview, and study material
  artifacts/          Demo recordings and local captures
  archive/            Old code snapshots, drafts, and source notes
  organization/       Move manifest and local cross-worktree inventory
```

Do not publish `.env` contents, live credentials, access tokens, real customer logs, database exports, private review findings, personal career notes, or machine-specific process state. Git ignore rules do not back up these files: maintain a separate private backup, including ignored material in every worktree.

Generated evaluation reports and per-case results remain at the paths used by their scripts, but are ignored. Only deliberately reviewed snapshots belong in `docs/evaluation/reports/`. Keep golden sets, evaluators, and metric tests tracked next to the code.

## Naming and Links

- Use English, lowercase kebab-case names for new shared files; use `README.md` as the topic index.
- Put reusable explanations in one authoritative guide. Link to it from plans and study notes.
- Prefer repository-relative Markdown links. Do not use `file:///`, drive letters, or links into ignored local folders in shared documentation.
- Keep source and export names descriptive. A draft diagram must be labeled as a draft, not described as generated from a different source.
- Use dates for evidence snapshots, not filenames such as `final-new-2.md`.
- When moving documents, repair their inbound links and their links to source code.

Run these offline checks from the repository root:

```shell
python scripts/check_docs.py
python -m unittest discover -s scripts/tests -p test_check_docs.py -v
git diff --check
```

The link checker validates local file destinations, portability, and references into ignored folders. It does not fetch external websites or certify API semantics, benchmark results, or heading fragments.

## Merge, Archive, or Delete

Merge overlapping explanations when they describe the same behavior, while retaining source evidence and important caveats. Keep designs and usage guides separate when they serve different readers. Archive obsolete plans with a clear status rather than applying their old instructions to the current system.

Delete a redundant copy only after checking its content hash against the retained file. Empty placeholders and editor backups can be discarded after confirming they contain no unique work. Do not discard a unique design, security review, or personal note merely because it looks old. Review generated logs, caches, and demo data separately from documentation cleanup.
