# System alarms

The `/alarms` page (it replaced Health) follows high-performance HMI practice (ISA-101 / ISA-18.2):
- Normal is neutral grey, and green never means "OK".
- Severity always has three cues: color, icon and word (Fault = red octagon, Warning = amber triangle).
- Times are shown in the site's time zone.
- There is no acknowledgement step: alarms raise and clear.

## Notifications
Each rule has `notify: { mobile, email }`. When the rule raises an alarm, a notification goes out
on every channel that is on: **mobile** push, **email**, both, or neither. The two toggles appear
in three places:
- the active alarms table, where they apply to the alarm's rule and so to all its future raises;
- the Rules dialog, which also has **Turn off all notifications**: after a confirmation, it turns both channels off on every rule;
- the rule builder.

The mock only stores the settings; the backend will send the notifications. Recipients (which
users or addresses) aren't modelled yet. A separate email section under Reports may later add
emails triggered by a combination of status and rules.

## Where the data comes from
The page reads one interface, `AlarmDataSource` (`data/AlarmDataSource.ts`). `data/source.ts`
picks the implementation, and today that is the in-memory mock in `src/mocks/alarms/`.

The mock is not a static list:
- Every point is a deterministic signal over time (`signals.ts`).
- Alarms come from running the real rule engine (`lib/ruleEngine.ts`) over those signals.
- A rule made in the UI therefore raises and clears like a live one.

## Connecting a live source
1. **Implement `AlarmDataSource`** in `src/api/alarms.ts` (the API layer; `src/api` never imports
   mocks). Map the calls onto backend-ot routes once they exist in its contract (see
   `docs/backend-gaps.md`, "System alarms"). Use `client.get/post/put` and the generated types.

   | Call | Suggested backend-ot route |
   |---|---|
   | `getSnapshot()` | `GET /api/alarms/snapshot?site_id=` (devices with last poll, point values and quality, rules, active + recent events, recent log, server time) |
   | `getSeries(pointId, from, to)` | `GET /api/device-point-readings/...` (the historian timeseries that already exists) |
   | `queryEvents(filter)` | `GET /api/alarms/events?site_id=&device_id=&severity=&rule_id=&from=&to=` |
   | `saveRule(rule)` | `PUT /api/alarm-rules/{id}` (includes `enabled` and `notify`) |
   | `subscribe(onChange)` | an SSE route (like the live stream's) or a WebSocket. Call `onChange` on every raise, clear, rule edit and poll. The page refetches the snapshot. |

2. **Evaluate rules on the server.** The browser only shows results. Keep the engine semantics:
   - an alarm raises after `delaySec` of continuous violation;
   - it clears past `threshold ± deadband`;
   - comms-stale means no successful poll for `staleAfterSec`;
   - every raise and clear is logged with its time;
   - a raise notifies on each channel on in the rule's `notify` (mobile push, email; both are backend work).

   `lib/ruleEngine.ts` and its tests are the reference.
3. **Validate rule names on the server too.** A rule's `name` becomes an identifier in backend-ot:
   - 1–150 characters, matching `^[A-Za-z_][A-Za-z0-9_]*$` (letters, digits, `_`, not starting
     with a digit);
   - unique ignoring case.

   The UI checks this with `lib/ruleName.ts`, and the mock rejects bad names the same way.
   `id` stays the stable key, so a name can change later without breaking references.
4. **Point `data/source.ts` at the live implementation**, then delete `src/mocks/alarms/` and its rows
   in `src/mocks/README.md` and `docs/backend-gaps.md`.

The snapshot's `now` is server time, so durations ("active for 8 min") don't depend on the
browser clock.
