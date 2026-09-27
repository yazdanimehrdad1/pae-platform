# powerflow: remaining items outside `services/powerflow/`

The registration is done:
- root `Makefile` `SERVICES` and the `down-all` / `stop-all` notes;
- `deploy/compose/dev.yaml`;
- root `.env.example`, root `CLAUDE.md` (services tree, port registry, `down-all`), and the `run-platform` skill;
- `contracts/openapi/powerflow.openapi.json`, `contracts/powerflow/points.json` and `contracts/README.md`.

What's left needs your decision. Delete this file once it's handled.

- [ ] **`TODO_MONOREPO_TASKS.md` "Next service":** mark powerflow as done (it was scaffolded with `new-service`). Keep open: optimizer, and the typed-client generator for a Python consumer.
- [ ] **Optional, `.claude/skills/new-service/templates/python/`:** powerflow adds `pyright` (dev dependency, blocking `make typecheck`, `[tool.pyright]` in `pyproject.toml`). Consider putting that in the template so new services get a real type checker (see TODO "Hardening").
- [ ] **Repo-wide note:** Starlette warns that `starlette.testclient` with `httpx` is deprecated in favour of `httpx2`. Switching would add a new dev dependency to every Python service, so it's left for a repo-wide decision.
- [ ] **Future:** move powerflow's profile scenarios from CSV files into its Postgres (you chose to keep them as CSV for now).
