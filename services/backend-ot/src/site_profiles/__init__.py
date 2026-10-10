"""
Site-specific historian functions, organised by role:

    declarations/       the standard shapes a profile is built from (SiteEndpoint, SiteAlarm,
                        DeviceHealthCheck, SiteProfile); no logic of their own
    common/             functions, calculations and health checks shared by every site
    individual_sites/   one package per site profile: its own functions and its profile.py
    profile_registry.py every known profile, validated when the app starts
"""
