"""A seed `--replace` locks every table the site delete can reach.

Invariant guarded: `site_cascade_tables()` is `sites` plus every table that references it,
directly or through another such table, read from the ORM's foreign keys. The replace locks these
before it deletes, so the poller, alarm job and report worker wait for it instead of deadlocking
(dev's 2bess_1pv replace deadlocked with the alarm job's insert into alarm_events). A new table
under a site is picked up without editing a list.
"""

from seed_db.seed_db import site_cascade_tables

from schemas.db_models.orm_models import Base


class TestSiteCascadeTables:
    def test_lists_sites_and_every_table_under_it(self) -> None:
        assert site_cascade_tables() == [
            "alarm_definitions",
            "alarm_evaluation_state",
            "alarm_events",
            "device_points",
            "device_points_readings",
            "devices",
            "profile_point_state",
            "pv_array_configs",
            "report_runs",
            "report_schedules",
            "report_templates",
            "site_slds",
            "sites",
        ]

    def test_includes_the_tables_background_jobs_write(self) -> None:
        # The poller writes readings and profile point state, the alarm job events and state,
        # the report worker runs.
        written_by_jobs = {
            "device_points_readings",
            "profile_point_state",
            "alarm_events",
            "alarm_evaluation_state",
            "report_runs",
        }
        assert written_by_jobs <= set(site_cascade_tables())

    def test_every_listed_table_exists_in_the_orm(self) -> None:
        assert set(site_cascade_tables()) <= set(Base.metadata.tables)
