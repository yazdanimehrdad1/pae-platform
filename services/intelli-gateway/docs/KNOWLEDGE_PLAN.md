# intelli-gateway: site knowledge, onboarding and answer cost (plan)

Agreed with the user on 2026-11-06. Not built yet. Read with [PROGRESS.md](PROGRESS.md) and
[CLAUDE.md](../CLAUDE.md). Build it step by step (section 8); update PROGRESS.md as steps land.

## 1. Principles

- **Everything the AI knows or can reach is in intelli-gateway.** The gateway is the one place that
  controls and limits the AI's information. backend-ot is not changed for the AI's needs, and the
  AI reaches it only through `services/backend_ot/`, only for approved devices and points, and
  only through allowlisted queries.
- **The gateway's Postgres is the only source of truth** for the AI's site knowledge.
- **Two ways in, one path:** the site admin in the web UI, and code-level seed modules. Both call
  the same `KnowledgeService` (validation, drafts, publish). No Excel import for now.
- **Keyed per site device, by point name:** (site_id, device_id, point_name). No equipment or
  vendor-model library: every site's guides are its own.
- **The AI uses only approved facts and published knowledge.**
- Out of scope (decided): per-item visibility tags; operating constraints (export limits, contract
  terms) in the knowledge; PDF upload (manuals are pasted text); declarative function formulas.

## 2. Site profile: the gateway's copy of backend-ot facts

What is copied (filtered from backend-ot's contract):

| backend-ot | copied | never copied |
|---|---|---|
| site | name, description, location, coordinates, time zone, capacity, operator | client_id, profile internals |
| devices | device_id, name, type, vendor, model, description | host, port, protocol, server address, scan ranges, timeouts, poll flags |
| points | name, category, class, unit, data type, enum and bitfield labels, severity, profile description | Modbus address, size, byte/word order, scale factor, record flags |
| SLD | the topology graph and its revision | layout/drawing data |
| PV arrays | DC/AC kW, tilt, azimuth, losses, temperature coefficient | |
| alarm definitions | name, kind, severity, message | rule expression, notification settings |

The admin adds what backend-ot doesn't have: ratings (e.g. BESS MW/MWh, inverter MVA) and device notes.

**Sync (option B: changes wait for approval).**
- A lifespan task polls backend-ot's catalog (about every 15 min, and when the admin opens the
  site) and stores a **pending diff**: devices/points added, removed or changed, a new SLD revision.
  It never changes the approved profile by itself.
- Until approved: an unapproved device or point is "not yet approved" to the AI; an approved
  point whose definition changed in backend-ot carries "definition changed, pending review" on its
  live values.
- Approving (whole diff or per item):
  - additions become coverage gaps (section 4)
  - a changed point marks its guides **needs review**
  - a removed point sets its guides aside (kept, not used)
  - because the key is the point name, a rename appears as remove + add, and the approval screen
    offers "this is a rename of X", which moves the guides to the new name
- A sync never deletes anything an engineer wrote.

## 3. What engineers author

| Type | Content | How the AI uses it |
|---|---|---|
| Point definition | meaning, unit note, normal range, related points | `explain_point` |
| Point guide: states | per enum value, bit or vendor fault code: label, severity, message, meaning, probable causes, checks, related points, safety note | `lookup_fault`, `explain_point`, flags on live values |
| Point guide: limits | above/below a value: severity, message, causes, checks | `explain_point`, flags on live values |
| Documents | manuals, IM scripts, procedures, experience notes (pasted Markdown, optional device and points) | manuals/scripts/procedures in the cached site block; notes via `search_experience_notes` |
| Site functions | a library function enabled for the site, its inputs bound to points | generic `list_site_functions` / `run_site_function` |

**Site functions (option B):** a Python library in `site_functions/` (functions only, like the
other feature folders): availability, round-trip efficiency, peer comparison, clipping, SOC drift,
and wrappers over backend-ot's site-function endpoints (through the allowlist). Each declares its
inputs (roles such as `charge_energy`) and its output unit. Per site, the admin enables a function
and binds each input to an approved point, then test-runs it. A new kind of function is a code
change with tests; enabling and binding is data. The tool list stays fixed (prompt cache stays
stable); the site's enabled functions are listed in its site block.

**Life cycle of every item:** draft → published → superseded/archived. Publishing writes a new
site knowledge version (content hash), which resets the site's prompt and answer caches.
Versions are kept (who, when, what changed) and can be rolled back.

## 4. Coverage report

`GET /api/v1/sites/{site_id}/knowledge/coverage`, the onboarding to-do list:
- approved alarm, enum and bitfield points without a guide (first priority), with the code count
- key analog points without limits
- devices without ratings, IM script or procedure
- enabled functions with unbound inputs
- pending sync diff count, guides needing review
- gaps the AI hit (section 6)

## 5. Onboarding a new site (the standard order)

1. The site exists in backend-ot (devices, points, SLD), as today.
2. Admin: **Onboard site**. The first sync diff (everything new) is reviewed and approved:
   profile version 1. Only now does the AI serve the site.
3. Add ratings and device notes.
4. Work the coverage report: definitions and state guides for alarm/enum/bitfield points, then
   limits, then site functions (enable + bind), then IM scripts and procedures.
5. Review drafts, publish.
6. "Try it": standard check questions, showing the answer, tools used, guides cited, cost.
7. Live. From then on: approve sync diffs, and grow the knowledge (section 6).

## 6. Growing the knowledge

- **Gap log:** every lookup that finds no guide is recorded (site, device, point, code, count) and
  ranked on the coverage report.
- **Conversation to note:** "Save as note" on a solved conversation creates a draft experience note.
- **Verified answers:** the admin marks a good answer as verified; matching questions are served
  from it without a Claude call.

## 7. Answer cost: cache and direct answers

1. **Direct lookups, no Claude:** fault-code search, point explain, note search as plain REST
   endpoints for the UI; a deterministic pre-router answers "what does fault X on DEVICE mean"
   from the guide, with "ask the AI to dig deeper".
2. **Answer cache** in Postgres. Key: site_id + normalized question (lower-cased, device and
   point names resolved against the approved profile, codes and time words extracted) + knowledge
   version + policy version + model/prompt version. Reuse depends on the tools the run used:
   knowledge-only answers until the next publish; live-data answers for a short TTL with
   "answer from HH:MM, refresh"; never across sites.
3. **Verified answers** (section 6).
4. **Cheaper Claude runs:** prompt caching (exists), model per run (Haiku for lookups, Opus for
   diagnosis), smaller tool results, per-site daily budgets.
- The admin sees and purges a site's cache from the UI.
- Measure first: log question, tools, tokens and cost per answer.
- Semantic (embedding) matching is not planned (no vector DB, needs a dependency).

## 8. Build order

Each step: provider first, `make contract` (additive), tests, PROGRESS.md updated.

1. **Site profile + sync** (built 2026-11-06, see PROGRESS.md item 7 and its leftovers):
   migration `005_site_profiles` (profile, pending diffs, approvals),
   the sync task, approval logic with rename handling; `services/backend_ot/` limited to approved
   devices/points and allowlisted queries. Tools read the approved profile.
2. **Knowledge store:** migration `006_knowledge` (point_definitions, point_states, point_limits,
   knowledge_documents, knowledge_versions), `KnowledgeService` (validate, draft, publish,
   rollback), Postgres + in-memory stores under one contract test, tools on published content,
   code-level seed loader (`make seed-knowledge site=...`, for real sites' knowledge; the
   service has no fictional sites at runtime).
3. **Admin API** under `/api/v1/sites/{site_id}/knowledge/...` (profile, diffs, items, publish,
   coverage), admin role only.
4. **Site functions:** `site_functions/` library, migration `007_site_functions` (enable +
   bindings), generic tools, test-run endpoint.
5. **web-plusdas Knowledge pages:** built alongside each step (the user's call, 2026-11-07), not
   all at the end. Done: "AI Site Profiles" (step 1: sites, pending changes, approve, what the AI
   knows, history). Next with their steps: ratings, points (definitions, states, limits),
   documents, functions, coverage, publish/history, try it.
6. **Persistent conversations** in Postgres, tied to the user; per-site grants for users and admins.
7. **Growth loop:** gap log, conversation to note, verified answers.
8. **Cost:** cost logging (can land earlier), direct lookups, answer cache, model per run, budgets.

The validator, everywhere: point names must be approved for the site; codes unique per point;
severity from the fixed list; function inputs bound to existing points with matching units; no
secrets (passwords, keys, IPs); size limits.
