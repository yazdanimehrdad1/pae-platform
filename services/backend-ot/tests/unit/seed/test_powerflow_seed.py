"""The powerflow dev seed is built from, and agrees with, powerflow's published contracts.

Invariant guarded: every point-standard device of a powerflow default site
(`contracts/powerflow/sites.json`) becomes one seeded device that reads powerflow's Modbus
server directly (host powerflow, port 502, unit 1, zero-based), and every register it serves
(`contracts/modbus/powerflow.registers.json`, powerflow_server yes/calc) becomes one NATIVE point
at base + offset with the contract's type and labels, its scale and unit converted to engineering
units (kW, kvar, kVA, kWh, kV; others as published); unserved registers are not
seeded. The site's single line diagram validates and links only points the seed creates.
Its standardized point links (load, BESS, PV, meters) join a template point to a served register
of the same device, with a scale that converts the register's stored unit.
Every PV device gets a PV array config with the contract's DC/AC ratings, and the site has a
location (coordinates with elevation) so it can be forecast. The
committed contracts are read as static fixtures (no DB/network).
"""

import pytest
from seed_db.powerflow_seed import (
    DEVICE_TYPES,
    KILO_UNITS,
    POWERFLOW_HOST,
    REGISTERS_CONTRACT,
    SITES_CONTRACT,
    build_seed,
    default_contract_path,
    device_name,
    engineering_unit,
    load_registers,
    load_sites,
    site_display_name,
)

from helpers.device_points.address_overlap import NativePointRange, validate_no_register_overlap
from helpers.device_points.device_standardized_points import generate_standardized_points
from helpers.device_points.standardized_point_links import power_scale_error
from schemas.api_models import SiteSld
from schemas.api_models.types import register_size
from schemas.tests_models import (
    PowerflowRegistersContract,
    PowerflowSitesContract,
    SeedData,
    SeedPointLink,
)

SITE = "2bess_1pv"


@pytest.fixture(scope="module")
def registers() -> PowerflowRegistersContract:
    return load_registers(default_contract_path(REGISTERS_CONTRACT))


@pytest.fixture(scope="module")
def sites() -> PowerflowSitesContract:
    return load_sites(default_contract_path(SITES_CONTRACT))


@pytest.fixture(scope="module")
def seed(registers: PowerflowRegistersContract, sites: PowerflowSitesContract) -> SeedData:
    return build_seed(SITE, registers, sites)


def build_sld(seed: SeedData) -> tuple[SiteSld, dict[str, set[str]]]:
    """The seed's SLD with fake ids, and which point names each device's link uses."""
    device_ids = {device.device.name: index + 1 for index, device in enumerate(seed.devices)}
    used: dict[str, set[str]] = {}

    def point_id(device: str, point: str) -> int:
        used.setdefault(device, set()).add(point)
        return hash((device, point)) % 100_000

    (sld,) = seed.site_slds(point_id, lambda device: device_ids[device]).values()
    return sld, used


class TestSite:
    def test_one_site_without_a_profile(self, seed: SeedData) -> None:
        (site,) = seed.sites
        assert site.name == "Powerflow 2BESS 1PV" == site_display_name(SITE)
        assert site.profile is None
        assert site.capacity == "5 MW / 20 MWh BESS + 5 MWac PV"

    def test_unknown_site_is_refused(self, registers, sites) -> None:
        with pytest.raises(ValueError, match="no default site"):
            build_seed("nope", registers, sites)


class TestDevices:
    def test_one_device_per_point_standard_device(self, seed: SeedData, sites) -> None:
        names = [device.device.name for device in seed.devices]
        assert names == [device_name(SITE, device) for device in sites.sites[SITE].devices]
        assert names == [
            "2bess_1pv-plant_controller", "2bess_1pv-bess1", "2bess_1pv-bess2", "2bess_1pv-pv1",
            "2bess_1pv-load1", "2bess_1pv-poi_meter", "2bess_1pv-m_bess1", "2bess_1pv-m_bess2",
            "2bess_1pv-m_pv1",
        ]

    def test_devices_read_powerflow_directly(self, seed: SeedData, registers, sites) -> None:
        kinds = {device_name(SITE, ref): ref.kind for ref in sites.sites[SITE].devices}
        for seeded in seed.devices:
            device = seeded.device
            assert device.host == POWERFLOW_HOST and device.port == registers.port == 502
            assert device.server_address == registers.unit_id == 1
            assert device.read_from_aggregator is False
            assert device.modbus_address_mode == "zero_based"
            assert device.type == DEVICE_TYPES[kinds[device.name]]


class TestPoints:
    def test_every_served_register_is_one_point_at_base_plus_offset(
        self, seed: SeedData, registers, sites
    ) -> None:
        for ref in sites.sites[SITE].devices:
            served = [
                register
                for register in registers.device_types[ref.kind].registers
                if register.powerflow_server != "no"
            ]
            points = seed.device_points[device_name(SITE, ref)]
            assert [point.name for point in points] == [register.point for register in served]
            for point, register in zip(points, served, strict=True):
                assert point.address == ref.base + register.offset
                assert point.data_type == register.data_type
                assert point.size == register_size(register.data_type) == register.width
                assert (point.scale_factor, point.unit) == engineering_unit(register)
                assert point.enum_detail == register.enum_detail
                assert point.bitfield_detail == register.bitfield_detail
                assert point.poll_kind == "holding" and point.word_order == "msw_first"

    def test_unserved_registers_are_not_seeded(self, seed: SeedData, registers) -> None:
        unserved = {
            register.point
            for register in registers.device_types["bess"].registers
            if register.powerflow_server == "no"
        }
        seeded = {point.name for point in seed.device_points["2bess_1pv-bess1"]}
        assert unserved and not unserved & seeded

    def test_no_points_overlap_on_a_device(self, seed: SeedData) -> None:
        for points in seed.device_points.values():
            validate_no_register_overlap(
                [
                    NativePointRange(
                        name=point.name, poll_kind=point.poll_kind or "holding",
                        address=point.address or 0, size=point.size,
                    )
                    for point in points
                ]
            )

    def test_engineering_units(self, seed: SeedData) -> None:
        """One raw count of a power/energy register is 1 kW/kvar/kVA/kWh; voltages read in kV."""
        bess = {point.name: point for point in seed.device_points["2bess_1pv-bess1"]}
        meter = {point.name: point for point in seed.device_points["2bess_1pv-poi_meter"]}
        assert (bess["W"].unit, bess["W"].scale_factor) == ("kW", 1.0)
        assert (bess["Var"].unit, bess["Var"].scale_factor) == ("kvar", 1.0)
        assert (bess["VA"].unit, bess["VA"].scale_factor) == ("kVA", 1.0)
        assert (bess["TotWhInj"].unit, bess["TotWhInj"].scale_factor) == ("kWh", 1.0)
        assert (bess["TotVarhInj"].unit, bess["TotVarhInj"].scale_factor) == ("kvarh", 1.0)
        assert (bess["LLV"].unit, bess["LLV"].scale_factor) == ("kV", 0.0001)  # 0.1 V counts
        assert (meter["PPV"].unit, meter["PPV"].scale_factor) == ("kV", 0.001)  # 1 V counts
        assert (meter["A"].unit, meter["A"].scale_factor) == ("A", 1.0)
        assert (bess["Hz"].unit, bess["SoC"].unit) == ("Hz", "%")

    def test_no_si_power_energy_or_voltage_units_remain(self, seed: SeedData) -> None:
        units = {point.unit for points in seed.device_points.values() for point in points}
        assert not units & set(KILO_UNITS)

    def test_classes(self, seed: SeedData) -> None:
        points = {point.name: point for point in seed.device_points["2bess_1pv-bess1"]}
        assert points["W"].point_class == "ANALOG"
        assert points["InvSt"].point_class == "BINARY"
        assert points["Alrm"].point_class == "ALARM" and points["Alrm"].severity == "LOW"


class TestSld:
    def test_validates_and_links_only_seeded_points(self, seed: SeedData) -> None:
        sld, used = build_sld(seed)
        SiteSld.model_validate(sld.model_dump())
        for device, point_names in used.items():
            seeded = {point.name for point in seed.device_points[device]}
            assert point_names <= seeded, device

    def test_meters_and_assets_are_linked(self, seed: SeedData) -> None:
        sld, used = build_sld(seed)
        linked = {node.id: node for node in sld.nodes if node.device is not None}
        assert set(linked) == {"poi_meter", "meter_m_bess1", "meter_m_bess2", "meter_m_pv1",
                               "bess1", "bess2", "pv1"}
        assert set(linked["poi_meter"].device.points) == {"vab", "vbc", "vca", "ia", "ib", "ic", "in"}
        assert set(linked["bess1"].device.points) == {"soc", "power", "mode"}
        assert used["2bess_1pv-bess1"] == {"SoC", "W", "InvSt"}

    def test_topology(self, seed: SeedData) -> None:
        sld, _ = build_sld(seed)
        types = {node.id: node.type for node in sld.nodes}
        assert types["utility"] == "grid" and types["poi"] == "poi"
        assert {types[f"tx_{asset}"] for asset in ("bess1", "bess2", "pv1")} == {"transformer"}
        assert types["load1"] == "load" and "tx_load1" not in types  # load1: on the POI bus
        assert {bus.id for bus in sld.buses} == {"poi_bus", "bus_mv1"}


@pytest.mark.parametrize("site", ["1bess_1pv", "2bess_1pv", "3bess_2pv"])
def test_every_default_site_builds(site: str, registers, sites) -> None:
    seed = build_seed(site, registers, sites)
    assert len(seed.devices) == len(sites.sites[site].devices)
    (sld,) = seed.site_slds(lambda _device, _point: 1, lambda _device: 1).values()
    assert sld.nodes


class TestPvArrays:
    def test_every_pv_device_has_its_contract_ratings(self, seed: SeedData, sites) -> None:
        site = sites.sites[SITE]
        pv_devices = [device for device in site.devices if device.kind == "pv"]
        assert pv_devices
        assert set(seed.pv_arrays) == {device_name(SITE, device) for device in pv_devices}
        pv_by_id = {pv.id: pv for pv in site.pv}
        for device in pv_devices:
            config = seed.pv_arrays[device_name(SITE, device)]
            assert config.dc_capacity_kw == pv_by_id[device.asset_id].dc_kwp
            assert config.ac_capacity_kw == pv_by_id[device.asset_id].p_max_kw

    def test_pv_arrays_belong_to_pv_devices(self, seed: SeedData) -> None:
        types = {seed_device.device.name: seed_device.device.type for seed_device in seed.devices}
        assert all(types[name] == "PV" for name in seed.pv_arrays)

    def test_site_has_a_location(self, seed: SeedData) -> None:
        (site,) = seed.sites
        assert site.coordinates is not None and site.coordinates.elevation_m is not None
        assert site.timezone != "UTC"


def resolve_links(seed: SeedData) -> list[tuple[SeedPointLink, tuple[str, str]]]:
    """Each link with its source as (device name, point name), resolved through fake ids."""
    names: dict[int, tuple[str, str]] = {}

    def point_id(device: str, point: str) -> int:
        names[len(names) + 1] = (device, point)
        return len(names)

    return [(link, names[link.link.source_point_id]) for link in seed.point_links(point_id)]


class TestPointLinks:
    def test_load_bess_pv_and_meters_are_linked(self, seed: SeedData) -> None:
        assert sorted((link.device_name, link.point_name, source) for link, (_, source) in resolve_links(seed)) == sorted([
            ("2bess_1pv-load1", "IED_ACTIVE_POWER", "W"),
            ("2bess_1pv-bess1", "BESS_ACTIVE_POWER", "W"),
            ("2bess_1pv-bess1", "BESS_STATE_OF_CHARGE", "SoC"),
            ("2bess_1pv-bess2", "BESS_ACTIVE_POWER", "W"),
            ("2bess_1pv-bess2", "BESS_STATE_OF_CHARGE", "SoC"),
            ("2bess_1pv-pv1", "PV_ACTIVE_POWER", "W"),
            ("2bess_1pv-poi_meter", "METER_ACTIVE_POWER", "W"),
            ("2bess_1pv-m_bess1", "METER_ACTIVE_POWER", "W"),
            ("2bess_1pv-m_bess2", "METER_ACTIVE_POWER", "W"),
            ("2bess_1pv-m_pv1", "METER_ACTIVE_POWER", "W"),
        ])

    def test_each_link_joins_a_template_point_to_a_served_register_of_its_device(self, seed: SeedData) -> None:
        types = {device.device.name: device.device.type for device in seed.devices}
        native = {(name, point.name): point for name, points in seed.device_points.items() for point in points}
        for link, (source_device, source_name) in resolve_links(seed):
            template = {point.name for point in generate_standardized_points(types[link.device_name], 1, 1)}
            assert link.point_name in template, link
            assert source_device == link.device_name, link
            source = native[(source_device, source_name)]
            assert power_scale_error(source.unit, link.link.unit, link.link.scale_factor) is None, link
