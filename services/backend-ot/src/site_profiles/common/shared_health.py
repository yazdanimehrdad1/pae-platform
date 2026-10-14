"""
Device health checks every device type shares, for SLD info boxes. None yet.

Each will be async (ctx: DeviceHealthContext) -> DeviceHealth, judging `ctx.device`; a site uses
one by declaring it in its profile.py. Device-specific checks go in common/<device type>/.
"""

"""

"""
