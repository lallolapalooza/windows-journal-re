# Session archive

`windows-journal-re-session.zip` is an **omp session archive** produced with
[`omp-archive`](https://github.com/alosslessdev/omp-archive-main). It contains
the complete analysis session: the main transcript, every tool and background
job output in full, the artifact tree, and a standalone `viewer.html`.

| Path | Contents |
|---|---|
| `manifest.json` | counts, sizes, omissions |
| `session.jsonl` | main transcript, byte-for-byte |
| `agents.json` | live agent state |
| `jobs.json` | background job records |
| `artifacts/` | untruncated tool/job logs |
| `viewer.html` | offline HTML viewer |

Unzip and open `viewer.html` to browse the analysis. The archive is not
redacted; review it before sharing beyond the repository.
