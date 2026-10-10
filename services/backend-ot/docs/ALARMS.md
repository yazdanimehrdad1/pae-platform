# How alarms work in backend-ot

This document explains the alarm feature from the top down. Read it in order: each section builds
on the one before.

---

## 1. The big picture in one paragraph

An **alarm definition** is a rule such as "battery temperature above 45 °C for 30 seconds".
A **background job** runs every 22 seconds. It checks every rule against the latest readings
stored in the database. When a rule becomes true, the job writes an **alarm event** ("raised at
10:02"). When the rule becomes false again, the job marks that event as cleared ("cleared at
10:15"). The UI reads the definitions and events through the `/api/alarms/...` routes.

```
   ┌──────────────────┐      every 22 seconds         ┌──────────────────┐
   │ alarm_definitions│ ───────────────────────────▶ │ evaluation job   │
   │ (the rules)      │                               │ (checks rules)   │
   └──────────────────┘                               └────────┬─────────┘
            ▲                                                  │ raise / clear
            │ create / edit                                    ▼
   ┌──────────────────┐                               ┌──────────────────┐
   │ UI  /  API       │ ◀──────── read ────────────── │ alarm_events     │
   └──────────────────┘                               │ (the history)    │
                                                      └──────────────────┘
```

---

## 2. The three database tables

| Table | One row per | What it holds |
|---|---|---|
| `alarm_definitions` | alarm rule | name, `source` (USER or PROFILE), `kind`, `rule` (JSON), severity, message, `enabled`, `notify_mobile`, `notify_email`, `deleted_at` |
| `alarm_events` | occurrence of an alarm | `raised_at`, `cleared_at` (empty while active), `value_at_raise`, device, severity, message |
| `alarm_evaluation_state` | alarm rule | `condition_since` (when the rule started holding, used for the delay), `last_evaluated_at` |

Two rules that the rest of the system relies on:

- **"Active" is not a column.** An alarm is active when it has an event whose `cleared_at` is empty.
  A database index allows at most one such event per alarm.
- **History belongs to the alarm.** Deleting a user alarm deletes its events too (cascade).

Models: `src/schemas/db_models/orm_models.py` (`AlarmDefinition`, `AlarmEvent`,
`AlarmEvaluationState`).

---

## 3. Where alarm definitions come from

Every definition has a `source`. There are two.

### 3a. USER alarms: created by people through the API

A user writes the rule in the UI. The API stores it. The user can edit or delete it freely.

There are three kinds of user rule:

| Kind | Raises when | Clears when | Waits `delay_sec` first? |
|---|---|---|---|
| `threshold` | one comparison is true: `point > 45`, `point > other_point`, or a bit test | the value is back past the limit by `deadband` (for `==`, `!=` and bit tests: as soon as it is false) | yes |
| `condition` | an ALL / ANY group of comparisons is true | as soon as the group is false | yes |
| `comms_stale` | a device has had no successful poll for `stale_after_sec` | the next successful poll | no |

**Deadband example.** Rule: `temperature > 45`, deadband `2`.
It raises at 46. It does **not** clear at 44.9. It clears only below 43. This stops an alarm from
flickering on and off when the value hovers around the limit.

Rule models: `src/schemas/api_models/alarms.py` (`ThresholdAlarm`, `ConditionAlarm`, `CommsStaleAlarm`).

#### What happens when a user creates an alarm

```
POST /api/alarms/site/{site_id}/definitions
        │
        ▼
  Lock the site row  (so two requests on the same site can't race)
        │
        ▼
  Does the site exist? ───── no ──▶ 404
        │ yes
        ▼
  Is the name free on this site? ───── no ──▶ 409
  (ignores case, checks user AND profile alarms)
        │ yes
        ▼
  Are the points / device the rule reads ───── no ──▶ 400
  active on this site? Do bit tests read bitfield points?
        │ yes
        ▼
  Is it enabled, and does the site already ───── yes ──▶ 409 (max_enabled = 20)
  have 20 enabled alarms?
        │ no
        ▼
  Save the row (source = USER)
```

Code: `src/helpers/alarms/definitions.py`.

### 3b. PROFILE alarms: written in Python code

A site profile, for example Alpha Solar, can declare alarms in code:

```python
SiteAlarm(
    key="placeholder_profile_alarm_1",   # stable id, never change it
    name="placeholder_profile_alarm_1",
    severity="fault",
    message="inverter_state is not mppt or derating",
    evaluate=placeholder_profile_alarm_1,  # async def (ctx: AlarmContext) -> AlarmCheck
)
```

The check is an ordinary async function that can read whatever it needs and returns
`AlarmCheck(active=True/False, value=..., device_id=...)`.

For the evaluation job to see a profile alarm, it must have a row in `alarm_definitions`. A
**sync** step creates and updates those rows:

```
  When the sync runs:                     What the sync does, per declared alarm (matched by key):
  ┌──────────────────────────┐
  │ • app startup (all sites)│            no row yet            ──▶ create it
  │ • a site is created      │ ──▶        name/severity/message
  │ • a site's profile       │              changed in code     ──▶ update the row
  │   changes                │            row was retired       ──▶ restore it
  └──────────────────────────┘            key no longer in code ──▶ retire it (soft delete,
                                                                    history is kept)
                                          a user alarm already
                                            has that name       ──▶ skip it and log a warning
```

A new or restored profile alarm starts **enabled** only if the site has fewer than 20 enabled
alarms. Otherwise it starts disabled.

What a user can change on a profile alarm: only `enabled`, `notify_mobile` and `notify_email`.
Users can't delete a profile alarm, only disable it.

Code: `src/helpers/alarms/profile_sync.py`, `src/site_profiles/declarations/alarm.py`,
example check in `src/site_profiles/individual_sites/alpha_solar/alpha_solar_alarms.py`
(a placeholder, not a real alarm yet).

---

## 4. The evaluation job: how alarms raise and clear

The scheduler registers a job named `alarm_evaluation`. It runs every
`ALARM_EVALUATION_INTERVAL_SECONDS` (default **22 s**, `src/config.py`). That is its own setting,
independent of Modbus polling (`POLL_INTERVAL_SECONDS`, default 10 s). **It never talks to devices. It
reads only the database.**

```
  alarm_evaluation job (every 22 s)
        │
        ▼
  For each site  ─────────────────────────────────────────────┐
        │                                                     │ if a site fails: log it,
        ▼                                                     │ continue with the next site
  1. Load the site's alarm definitions, its active events,    │
     and each alarm's evaluation state.                       │
        │                                                     │
        ▼                                                     │
  2. Collect the inputs the enabled alarms need:              │
       • latest reading of every point they watch             │
         (treated as missing if older than input_max_gap)     │
       • last successful poll time of every watched device    │
        │                                                     │
        ▼                                                     │
  3. For each alarm:                                          │
       disabled?  ──▶ clear it if it was active               │
       PROFILE    ──▶ run its Python check                    │
       threshold / condition / comms_stale ──▶ test the rule  │
        │                                                     │
        ▼                                                     │
  4. Feed the result into the state machine (section 5).      │
     It answers: RAISE, CLEAR, or nothing.                    │
        │                                                     │
        ▼                                                     │
  5. RAISE  ──▶ insert a row in alarm_events                  │
               (and log which notifications WOULD be sent)    │
     CLEAR  ──▶ set cleared_at on the active event            │
     Always ──▶ save condition_since / last_evaluated_at      │
        │                                                     │
        ▼                                                     │
  6. Commit (one transaction per site) ───────────────────────┘
```

If one alarm's check throws an error, the job logs it and skips only that alarm.

Code: `src/scheduler/engine.py` (registration), `src/helpers/alarms/evaluation.py` (the cycle).

---

## 5. The state machine: when exactly does an alarm raise?

Each alarm is in one of three states. The pure function `step()` in
`src/helpers/alarms/engine.py` moves it between them. That file has no database access and no
clock, so it is easy to test.

```
                         rule true, delay = 0  ──▶ RAISE
              ┌────────────────────────────────────────────────────┐
              │                                                    ▼
        ┌──────────┐   rule true, delay > 0   ┌───────────┐  held for delay  ┌──────────┐
        │   IDLE   │ ───────────────────────▶ │  PENDING  │ ──────────────▶ │  ACTIVE  │
        │          │                          │ (waiting) │     RAISE        │          │
        └──────────┘ ◀─────────────────────── └───────────┘                  └──────────┘
              ▲        rule false, OR                                             │
              │        data missing (timer resets)                                │
              │                                                                   │
              └───────────────────────────────────────────────────────────────────┘
                   clear test passes, OR alarm disabled, OR its rule edited  ──▶ CLEAR
```

The three rules worth remembering:

1. **The delay requires continuous truth.** If the rule is false even once while PENDING, the timer
   starts over.
2. **Missing data never raises or clears.** If an input reading is missing or too old, an ACTIVE
   alarm stays active, and a PENDING alarm goes back to IDLE (timer reset).
3. **Profile alarms and comms-stale have no delay.** They raise on the first cycle the check is true.

### Worked example

Rule: `battery_temp > 45`, `delay_sec = 30`, `deadband = 2`. The job runs every 22 s.

| Time | battery_temp | State before | What happens | State after |
|---|---|---|---|---|
| 10:00:00 | 44 | IDLE | rule false | IDLE |
| 10:00:22 | 46 | IDLE | rule true, start timer | PENDING (since 10:00:22) |
| 10:00:44 | 47 | PENDING | 22 s held, not enough | PENDING |
| 10:01:06 | 46 | PENDING | 44 s held → **RAISE**, event row created | ACTIVE |
| 10:01:28 | 44 | ACTIVE | 44 is not below 43 (45 − 2), stay active | ACTIVE |
| 10:01:50 | 42 | ACTIVE | 42 < 43 → **CLEAR**, `cleared_at` set | IDLE |

Note the raise came 44 s after the condition started, not 30 s: the job only looks every 22 s, so
a delay is rounded up to the next cycle.

---|---|---|---|---|
| 10:00:00 | 44 | IDLE | rule false | IDLE |
| 10:00:10 | 46 | IDLE | rule true, start timer | PENDING (since 10:00:10) |
| 10:00:20 | 47 | PENDING | 10 s held, not enough | PENDING |
| 10:00:30 | 46 | PENDING | 20 s held, not enough | PENDING |
| 10:00:40 | 46 | PENDING | 30 s held → **RAISE**, event row created | ACTIVE |
| 10:00:50 | 44 | ACTIVE | 44 is not below 43 (45 − 2), stay active | ACTIVE |
| 10:01:00 | 42 | ACTIVE | 42 < 43 → **CLEAR**, `cleared_at` set | IDLE |

---

## 6. What editing an alarm does to an active event

| Change | Effect |
|---|---|
| Rule changed | The active event is cleared, and the delay timer is wiped. The new rule starts fresh. |
| Disabled | The active event is cleared. |
| Enabled | Allowed only if the site has fewer than 20 enabled alarms (else 409). |
| Name, severity, message, notifications | No effect on an active event. |
| Deleted (user alarms only) | The definition, all its events and its state are removed. |

---

## 7. API routes

All routes are under `/api/alarms/site/{site_id}/`. Router: `src/api/routers/alarms.py`.

| Method and path | Returns |
|---|---|
| `GET snapshot` | everything the Alarms page needs now: all definitions, active events, events cleared in the last 6 hours, and a log of raises and clears in that window |
| `GET events?start_time=&end_time=` | history: every event that overlaps the range. Filters: device, severity, definition |
| `GET definitions` | the site's alarms (user and profile) |
| `POST definitions` | create a user alarm |
| `PUT definitions/{alarm_id}` | update an alarm (only the fields you send) |
| `DELETE definitions/{alarm_id}` | delete a user alarm |

---

## 8. Not the same thing: ALARM-class points

There is a second, unrelated feature that also uses the word "alarm".

```
  device points with point_class = "ALARM"
        │
        ▼
  GET /api/sites/{site_id}/health        (src/helpers/sites/site_health.py)
        │
        ▼
  "Which alarm points read non-zero right now?"  (for bitfields: which bits are set)
  computed on each request; nothing is stored; no delay, no history
```

It does **not** create rows in `alarm_events`. To get history for one of those points, create a
`threshold` alarm on it, for example a bit test.

---

## 9. Not built yet

- **Notifications are not sent.** On a raise, the job only logs `would notify: mobile, email`.
- **Profile alarms are placeholders.** Alpha Solar's only profile alarm is an example.
- **The two alarm features are separate.** ALARM-class points and alarm rules share no code or
  storage.

---

## 10. File map

| File | Responsibility |
|---|---|
| `src/schemas/api_models/alarms.py` | rule shapes, request/response models, limits (`MAX_ENABLED_ALARMS = 20`, `RECENT_WINDOW_HOURS = 6`) |
| `src/schemas/db_models/orm_models.py` | the three tables |
| `src/helpers/alarms/definitions.py` | create / update / delete / list definitions, with their checks |
| `src/helpers/alarms/profile_sync.py` | keep PROFILE rows in step with code |
| `src/helpers/alarms/engine.py` | the pure state machine (`step`) and the rule tests |
| `src/helpers/alarms/evaluation.py` | one evaluation cycle: read inputs, run the engine, write events |
| `src/helpers/alarms/events.py` | read events: snapshot, history, per-device counts |
| `src/api/routers/alarms.py` | HTTP routes |
| `src/scheduler/engine.py`, `src/scheduler/jobs.py` | register and run the `alarm_evaluation` job |
| `src/site_profiles/declarations/alarm.py` | `SiteAlarm`, the shape of a profile alarm |
| `src/helpers/sites/site_health.py` | the separate ALARM-class points feature (section 8) |
