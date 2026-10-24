"""changed_services: a service is checked when its files, a contract it provides or consumes, or
shared CI tooling changed; images exist only for the four deployed services, never mock-modbus or
mobile-plusdas. Run: uv run --no-project python -m unittest discover -s scripts/ci"""

import json
import unittest

from changed_services import (
    CONTRACT_USERS,
    IMAGES,
    REPO_ROOT,
    SERVICES,
    build_outputs,
    select_services,
)

ALL = [service.service for service in SERVICES]


class SelectServices(unittest.TestCase):
    def test_a_service_file_selects_only_that_service(self) -> None:
        self.assertEqual(select_services(["services/powerflow/src/powerflow/app.py"]), ["powerflow"])

    def test_a_contract_selects_its_provider_and_consumers(self) -> None:
        self.assertEqual(
            select_services(["contracts/openapi/backend-ot.openapi.json"]),
            ["backend-ot", "web-plusdas", "mobile-plusdas", "intelli-gateway"],
        )

    def test_contract_docs_select_nothing(self) -> None:
        self.assertEqual(select_services(["contracts/README.md"]), [])

    def test_shared_ci_tooling_selects_everything(self) -> None:
        for path in (".github/workflows/ci.yml", "scripts/ci/smoke_image.sh", "Makefile"):
            with self.subTest(path=path):
                self.assertEqual(select_services([path]), ALL)

    def test_root_docs_and_deploy_plan_select_nothing(self) -> None:
        self.assertEqual(select_services(["README.md", "deploy/PLAN.md", "CLAUDE.md"]), [])

    def test_the_dev_stack_compose_selects_nothing(self) -> None:
        self.assertEqual(select_services(["deploy/compose/dev.yaml"]), [])

    def test_order_follows_the_service_list(self) -> None:
        self.assertEqual(
            select_services(["services/intelli-gateway/x.py", "services/backend-ot/y.py"]),
            ["backend-ot", "intelli-gateway"],
        )

    def test_every_contract_user_is_a_known_service(self) -> None:
        for users in CONTRACT_USERS.values():
            self.assertLessEqual(set(users), set(ALL))

    def test_an_unknown_contract_selects_everything(self) -> None:
        self.assertEqual(select_services(["contracts/openapi/optimizer.openapi.json"]), ALL)

    def test_every_contract_file_is_mapped(self) -> None:
        contracts = REPO_ROOT / "contracts"
        files = {path.relative_to(contracts).as_posix() for path in contracts.rglob("*.json")}
        self.assertEqual(files, set(CONTRACT_USERS))


class BuildOutputs(unittest.TestCase):
    def test_images_only_for_deployed_services(self) -> None:
        images = json.loads(build_outputs(ALL)["images"])
        self.assertEqual(
            [image["service"] for image in images],
            ["backend-ot", "intelli-gateway", "powerflow", "web-plusdas"],
        )

    def test_dev_only_and_mobile_never_get_an_image(self) -> None:
        self.assertNotIn("mock-modbus", {image.service for image in IMAGES})
        self.assertNotIn("mobile-plusdas", {image.service for image in IMAGES})

    def test_images_build_from_their_own_directory(self) -> None:
        for image in IMAGES:
            self.assertEqual(image.context, f"services/{image.service}")
            self.assertTrue(image.dockerfile.startswith(f"{image.context}/"))

    def test_services_carry_toolchain_and_integration(self) -> None:
        services = json.loads(build_outputs(["backend-ot", "web-plusdas"])["services"])
        self.assertEqual(
            services,
            [
                {"service": "backend-ot", "toolchain": "python", "integration": True},
                {"service": "web-plusdas", "toolchain": "node", "integration": False},
            ],
        )

    def test_nothing_selected_gives_empty_lists(self) -> None:
        self.assertEqual(build_outputs([]), {"services": "[]", "images": "[]"})


if __name__ == "__main__":
    unittest.main()
