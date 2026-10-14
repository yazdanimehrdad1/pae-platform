"""
Reports: templates (what a report contains), runs (a queued or generated report) and their stored
results (snapshots), served under /api/reports.

The module is self-contained: its models are in schemas/reports/, its tables in migration 014, its
router in api/routers/reports.py, its scheduler job in jobs.py. It reads the data it reports on only
through reports.data_source.ReportDataSource (backend_ot_source.py implements it in process).
"""
