"""The accounts an environment's configuration asks for, made sure of at startup: the first
admin (only while there are no users) and, on the dev stack and the dev cloud, the demo
login. Passwords never get logged."""

import logging

from intelli_gateway.auth.service import AuthService
from intelli_gateway.config import Settings

logger = logging.getLogger(__name__)


async def ensure_configured_accounts(auth: AuthService, settings: Settings) -> None:
    if settings.bootstrap_admin_password is not None:
        admin = await auth.ensure_bootstrap_admin(
            settings.bootstrap_admin_email,
            settings.bootstrap_admin_password.get_secret_value(),
        )
        if admin is not None:
            logger.info("bootstrap_admin_created", extra={"fields": {"email": admin.email}})
    if settings.demo_user_password is not None:
        email = settings.demo_user_email
        if await auth.ensure_demo_user(email, settings.demo_user_password.get_secret_value()):
            logger.info("demo_user_updated", extra={"fields": {"email": email}})
