# System alarms

The `/alarms` page (it replaced Health) follows high-performance HMI practice (ISA-101 / ISA-18.2):
- Normal is neutral grey, and green never means "OK".
- Severity always has three cues: color, icon and word (Fault = red octagon, Warning = amber triangle).
- There is no acknowledgement step: alarms raise and clear.

## Where the data comes from
backend-ot defines, evaluates and stores alarms. This page only shows and configures them, for
the site chosen in the site picker. `hooks/useAlarmsData.ts` combines three reads, and
`lib/pageData.ts` maps them into the page model (`types.ts`):

| Read | Call | Refresh |
|---|---|---|
| Alarms, active events plus those cleared in 6 h, the raise/clear log, server time | `alarmsApi.getSnapshot` → `GET /api/alarms/site/{id}/snapshot` | every 10 s |
| Devices and their points | `devicesApi.getRecords` → `GET /api/devices/site/{id}/devices` | every 60 s |
| Point values; a device's last poll is its newest native reading | `historianApi.getLatestReadings` (per device) | every 10 s |
| Trend of a point | `historianApi.getDevicePointReadings` (timeseries) | every 10 s |
| History drawer | `alarmsApi.queryEvents` → `GET /api/alarms/site/{id}/events` | on open and on filter change |

Durations ("active for 8 min") are measured against the snapshot's server `now`. Times show in the
browser's time zone, because sites have none yet (`docs/backend-gaps.md`).

## Alarms: two sources
- **User rules** are built in the rule builder (`components/RuleBuilder.tsx`). There are three kinds:
  - **threshold**: one point against a value or another point, or a bit test; with a delay and a deadband;
  - **condition**: ALL/ANY groups over several points, with a delay. It uses the shared condition
    editor, the same one virtual points use (`src/shared/components/conditions/`);
  - **comms stale**: a device with no successful poll for N seconds.
- **Profile alarms** are defined in code, in backend-ot's site profile. Their logic, name,
  severity and message are read-only here.

For each alarm, the user picks:
- **Enabled**: an enabled alarm is evaluated by backend-ot and its alarms show in Active alarms.
  A disabled alarm raises nothing, and backend-ot clears its active event. At most 20 alarms per
  site can be enabled (`MAX_ENABLED_ALARMS`; backend-ot answers 409 past it). A new rule, or a
  profile alarm synced onto a full site, starts disabled.
- **Notifications**: mobile and/or email. They are stored now; backend-ot only logs them and
  doesn't send anything yet.

The Rules dialog (`components/RuleManager.tsx`) shows each alarm in full:
- source and kind;
- the condition in words, with real point and device names;
- message, delay, deadband or timeout;
- when it was created and updated;
- its switches.

**Delete** is offered only for user rules. After a confirmation, it permanently removes the rule
**and its whole alarm history**. Profile alarms can't be deleted, only disabled.

Rule names are identifiers: 1–150 characters, `^[A-Za-z_][A-Za-z0-9_]*$`, unique per site
ignoring case. The UI checks them with `lib/ruleName.ts`, and backend-ot checks them again.
