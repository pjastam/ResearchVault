# Backend: none — stopping at raw/

The honest option: ResearchVault builds canonical bundles and stops. You run whatever wiki tooling you like against `raw/`, on your own schedule.

```toml
confidential = false
backend      = "none"

[backends.none]
invocation = "cli"
locality   = "local"
```

No verbs are declared, so every dispatcher call returns `skipped` — not an error. The bundle was written; that was the job.

This is also the cleanest way to test whether the contract holds. If a fresh tool can rebuild a useful wiki from `raw/` alone, the coupling really is as loose as it claims to be.
