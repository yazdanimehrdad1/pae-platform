# Reports

A site's report templates and generated reports, from backend-ot's `/api/reports/site/{site_id}/...`.

- **`ReportsPage`** (`/reports?site=<id>`): the templates, each with **Generate** (queues a report)
  and **Customize** (opens it in the builder), **New report**, and the reports, newest first. The
  list polls every 2 s while a report is queued or generating.
- **`ReportBuilderPage`** (`/reports/:siteId/builder[?template=<id>]`): name, period and sections.
  **Generate report** sends the template (with the period as an override if only that changed), or
  the definition inline once a section changed (`lib/draft.ts` `runRequest`), then opens the report.
  **Save** updates the template (a changed definition bumps its version); **Save as new template**.
  Unfinished sections are listed by `draftProblems` and block sending; backend-ot's 400 `errors`
  ("<block id>: ...") show on their section. A custom period is typed in the site's time zone
  (`lib/zonedTime.ts`). One editor per block kind in `components/builder/BlockEditors.tsx`.
- **`ReportViewPage`** (`/reports/:siteId/runs/:runId`): one report, rendered **only from its stored
  snapshot** (`run.result`), so it shows the same numbers every time it is opened.

## Exports (only on request)
- **Export PDF** opens the browser's print dialog ("Save as PDF"). Print styles hide the app frame
  (sidebar, notes) and the buttons, and `usePrintInLightTheme` prints in the light theme. No PDF
  is generated or stored anywhere else.
- **CSV** per table and **JSON** for the whole report are built in the browser (`lib/csv.ts`).

## Blocks
One renderer per block kind in `components/blocks/`, chosen in `components/ReportView.tsx`. A block
that failed to generate carries `error` and is shown as a message; the rest of the report renders.
Chart series keep their own sample times (null values are gaps the line breaks at); a bar chart
merges them by time (`lib/chartData.ts`).

## Text variables
A text section can name the site, any device and any point of the site. backend-ot fills them in when
the report is generated (its `reports/text_variables.py`; the catalog lists them):
`{site_name}`, `{window_start}` ... · `{device:12.name}`, `{device:12.type}` ... ·
`{point:34.name}`, `{point:34.unit}`, `{point:34.max}` (statistics cover the report's period).
Devices and points are named by id, so a renamed device still shows its current name. The editor's
**Insert a variable** menu writes them at the cursor, and its preview shows names filled in
(`lib/textVariables.ts`). A typo or an id not on the site is a 400 on that section.

Times are shown in the site's time zone (`site.timezone`, and the snapshot's `timezone` for a report).

## Schedules
The Schedules card lists the site's schedules (`components/ScheduleList.tsx`): when each one generates
which template ("Every Monday and Friday at 07:30", on the site's clock), what it keeps, and when it
next runs; a switch turns one off. **Schedule** on a template, or **New schedule**, opens
`ScheduleDialog`: template, cadence (hourly / daily / weekly / monthly), the period each report covers
(the template's, or another), and retention (keep the last N, and/or N days; only the schedule's own
reports are pruned). backend-ot's `report_schedule_dispatch` job queues each due report, and
`report_worker` generates it; scheduled reports are marked "Scheduled" in the list.
