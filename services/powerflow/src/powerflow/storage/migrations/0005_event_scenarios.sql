-- Event scenarios: per-site timelines of injected conditions (breaker operations, asset faults,
-- comm loss, grid events), played by the engine. A scenario belongs to one site and goes with it.
CREATE TABLE IF NOT EXISTS event_scenarios (
    site        TEXT NOT NULL REFERENCES sites (name) ON DELETE CASCADE ON UPDATE CASCADE,
    name        TEXT NOT NULL,
    scenario    JSONB NOT NULL,          -- an EventScenario, validated by the app before writing
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (site, name)
);
