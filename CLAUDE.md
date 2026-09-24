# pae-platform

Monorepo for the PAE platform services (`services/<name>/`), their shared contracts
(`contracts/`), the local dev stack (`deploy/compose/`) and e2e checks (`scripts/e2e/`).

**Start here:** `MONOREPO_ROADMAP.md` is the living plan for setting this monorepo up. Read
its Master roadmap table (what's done, what's next) and the bottom of its Decision & change log
before starting work, and record decisions/deviations there in the same change as the work.
This file is a placeholder until roadmap Phase 5 writes the full agent rules.

Hard rules already in force:
- Services never import each other's code or read each other's files; they talk over the
  network and share only `contracts/` (see `contracts/README.md`).
- Work inside one service at a time and follow its own `services/<svc>/CLAUDE.md`.
- `services/mock-modbus` is DEV-ONLY — never in a production manifest.
- Deployment (CI/CD, k8s, ArgoCD) is out of scope for now: don't edit `services/*/.github/`,
  `services/*/k8s/` or deploy scripts unless asked.
- Commands: `make help` at the root; `make -C services/<svc> help` per service; the
  `run-platform` skill for running the stack.
