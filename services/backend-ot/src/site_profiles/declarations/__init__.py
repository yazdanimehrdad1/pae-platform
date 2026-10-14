"""
Declarations: the standard shapes a site profile is built from. They hold no logic of their own.

Each is a frozen Pydantic model that points at an async function living in site_profiles/common/
(shared) or site_profiles/individual_sites/<site>/ (site-specific), and checks at import time that
the function is `async def`. profile_registry.py validates the rest when the app starts.

    endpoint.py   SiteEndpoint       a function served at a URL       (SiteController signature)
    alarm.py      SiteAlarm          a check that raises/clears alarm (AlarmEvaluator signature)
    health.py     DeviceHealthCheck  a health verdict for SLD boxes   (HealthEvaluator signature)
    profile.py    SiteProfile        one site's endpoints, alarms and health checks together
"""
