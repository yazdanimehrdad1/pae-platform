"""Engineer knowledge for powerflow's simulated 2bess_1pv site (the dev stack's
"Powerflow 2BESS 1PV"): the code-level way in, next to the admin UI. Simulated plant, no real
plant data.

A few of each kind, written so the AI can answer typical engineer questions well: device ratings,
point guides for the status, alarm and key analog points, four documents, and site prompts that
link nothing, only points, only documents, or points, documents, functions and ratings together.

Devices are found by name in the approved profile (their ids differ per database). Documents and
prompts have fixed ids, so seeding again changes nothing unless this file changed.
"""

from datetime import UTC, datetime

from intelli_gateway.schemas.knowledge import (
    DeviceFacts,
    DeviceRating,
    GuideSeverity,
    KnowledgeDocument,
    KnowledgeKind,
    LimitCondition,
    LimitGuide,
    NormalRange,
    PointGuide,
    PromptPointLink,
    SiteKnowledge,
    SitePrompt,
    SitePromptLinks,
    StateGuide,
    StateKind,
)
from intelli_gateway.schemas.site_profile import SiteCatalog
from intelli_gateway.utils.exceptions import InvalidRequestError

SITE_NAME = "Powerflow 2BESS 1PV"

# The import replaces site_id, author and updated_at; these are placeholders.
_SITE = 0
_AT = datetime(2026, 11, 11, tzinfo=UTC)

_PLANT_CONTROLLER = "2bess_1pv-plant_controller"
_BESS = ("2bess_1pv-bess1", "2bess_1pv-bess2")
_PV = "2bess_1pv-pv1"
_POI_METER = "2bess_1pv-poi_meter"

DOC_BESS_MANUAL = "seed-2bess-1pv-bess-manual"
DOC_BESS_RESET_SCRIPT = "seed-2bess-1pv-bess-reset-script"
DOC_PV_CURTAILMENT_PROCEDURE = "seed-2bess-1pv-pv-curtailment-procedure"
DOC_FAN_NOTE = "seed-2bess-1pv-bess2-fan-note"

FAULT, WARNING, INFO = GuideSeverity.FAULT, GuideSeverity.WARNING, GuideSeverity.INFO
ENUM, BIT = StateKind.ENUM_VALUE, StateKind.BIT


def _device_ids(catalog: SiteCatalog) -> dict[str, int]:
    by_name = {device.name: device.device_id for device in catalog.devices}
    wanted = (_PLANT_CONTROLLER, *_BESS, _PV, _POI_METER)
    missing = [name for name in wanted if name not in by_name]
    if missing:
        raise InvalidRequestError(
            f"not the 2bess_1pv site, or its profile lacks devices: {', '.join(missing)}"
        )
    return {name: by_name[name] for name in wanted}


# --- device ratings (what backend-ot doesn't hold) ------------------------------------------------


def _facts(ids: dict[str, int]) -> list[DeviceFacts]:
    bess = [
        DeviceFacts(
            site_id=_SITE,
            device_id=ids[name],
            ratings=(
                DeviceRating(name="Rated power (charge and discharge)", value=2.5, unit="MW"),
                DeviceRating(name="Energy capacity", value=10, unit="MWh"),
                DeviceRating(name="Inverter apparent power", value=2.75, unit="MVA"),
                DeviceRating(name="Usable SoC window, low", value=5, unit="%"),
                DeviceRating(name="Usable SoC window, high", value=95, unit="%"),
                DeviceRating(name="Round-trip efficiency (AC, design)", value=90, unit="%"),
                DeviceRating(name="Ramp rate limit", value=500, unit="kW/s"),
                DeviceRating(name="Step-up transformer", value=2750, unit="kVA"),
            ),
            notes=(
                "4-hour battery: 10 MWh at 2.5 MW. The usable window 5-95 % holds 9 MWh, so a full "
                "discharge from 95 % takes about 3.6 h at rated power. Auxiliary load (HVAC, "
                "controls) is about 15 kW, drawn from the inverter's 480 V bus."
            ),
            updated_at=_AT,
        )
        for name in _BESS
    ]
    return [
        *bess,
        DeviceFacts(
            site_id=_SITE,
            device_id=ids[_PV],
            ratings=(
                DeviceRating(name="AC rating", value=5.0, unit="MW"),
                DeviceRating(name="DC array", value=6.5, unit="MWp"),
                DeviceRating(name="DC/AC ratio", value=1.3, unit="ratio"),
                DeviceRating(name="Inverter apparent power", value=5.5, unit="MVA"),
                DeviceRating(name="Step-up transformer", value=5500, unit="kVA"),
            ),
            notes=(
                "DC/AC 1.3: on clear days around solar noon the array can deliver more than 5 MW, "
                "so output flat at 5,000 kW is clipping, not curtailment or a fault."
            ),
            updated_at=_AT,
        ),
        DeviceFacts(
            site_id=_SITE,
            device_id=ids[_PLANT_CONTROLLER],
            ratings=(
                DeviceRating(name="Combined generation nameplate (PV + BESS)", value=10, unit="MW"),
                DeviceRating(name="PV nameplate", value=5, unit="MW"),
                DeviceRating(name="BESS power (2 x 2.5 MW)", value=5, unit="MW"),
                DeviceRating(name="BESS energy (2 x 10 MWh)", value=20, unit="MWh"),
                DeviceRating(name="POI nominal voltage", value=12.47, unit="kV"),
                DeviceRating(name="Nominal frequency", value=60, unit="Hz"),
            ),
            notes=(
                "The site record's 5,000 kW capacity is the PV nameplate. PV and both batteries "
                "together can export up to 10 MW at the POI, less the site load and losses."
            ),
            updated_at=_AT,
        ),
    ]


# --- point guides ---------------------------------------------------------------------------------

_INVERTER_STATES = (
    StateGuide(kind=ENUM, code=3, label="RUNNING", severity=INFO, message="Running normally"),
    StateGuide(
        kind=ENUM,
        code=4,
        label="THROTTLED",
        severity=INFO,
        message="Running, limited by a ramp, SoC or curtailment limit",
        meaning=(
            "Normal operation, not a fault: the inverter holds back power because of its ramp "
            "limit, an SoC limit (BESS) or a plant controller limit (PV)."
        ),
        checks=(
            "BESS: is SoC near 5 % or 95 %?",
            "PV: which bits are set in ThrotSrc?",
        ),
    ),
    StateGuide(
        kind=ENUM,
        code=6,
        label="FAULT",
        severity=FAULT,
        message="Inverter tripped: no power until the cause is cleared and the alarm reset",
        meaning=(
            "The inverter opened its AC contactor. Faults latch: the state stays FAULT after the "
            "cause has gone, until an alarm reset."
        ),
        probable_causes=(
            "Over-temperature",
            "Ground fault",
            "DC over- or undervoltage",
            "Contactor error",
            "Cabinet door opened or emergency stop",
        ),
        checks=(
            "Read Alrm (and Evt1 on a BESS) to see which cause tripped it",
            "Follow the 'BESS fault: reset and restart' script",
        ),
        related_points=("Alrm", "Evt1"),
        safety_note=(
            "A ground fault or an open cabinet door needs a site visit: never reset it remotely "
            "without the site technician's confirmation."
        ),
    ),
    StateGuide(
        kind=ENUM,
        code=7,
        label="STANDBY",
        severity=INFO,
        message="Ready, no power commanded",
    ),
    StateGuide(
        kind=ENUM,
        code=0,
        label="OFF",
        severity=WARNING,
        message="Inverter off (stopped by command)",
    ),
)


def _bess_guides(device_id: int) -> list[PointGuide]:
    return [
        PointGuide(
            site_id=_SITE,
            device_id=device_id,
            point_name="InvSt",
            meaning="The battery inverter's operating state (SunSpec 701 InvSt).",
            related_points=("ChaSt", "SoC", "Alrm", "Evt1"),
            states=_INVERTER_STATES,
            updated_at=_AT,
        ),
        PointGuide(
            site_id=_SITE,
            device_id=device_id,
            point_name="SoC",
            meaning="The battery's state of charge, % of its 10 MWh capacity.",
            unit_note="% of 10 MWh: 1 % is 100 kWh.",
            normal_range=NormalRange(
                min=10, max=90, note="Kept within 5-95 % by the controller; 10-90 % is comfortable."
            ),
            related_points=("ChaSt", "InvSt", "W"),
            limits=(
                LimitGuide(
                    condition=LimitCondition.BELOW,
                    value=10,
                    severity=WARNING,
                    message="SoC low: discharge will stop at 5 %",
                    probable_causes=(
                        "Long discharge (evening peak)",
                        "Not recharged by PV during the day",
                    ),
                    checks=("Is the BESS charging in the next PV window?",),
                ),
                LimitGuide(
                    condition=LimitCondition.ABOVE,
                    value=90,
                    severity=INFO,
                    message="SoC high: charging will stop at 95 %",
                ),
            ),
            updated_at=_AT,
        ),
        PointGuide(
            site_id=_SITE,
            device_id=device_id,
            point_name="Evt1",
            meaning=(
                "Battery events (SunSpec 802 Evt1): *_ALARM bits trip the battery, *_WARNING bits "
                "derate it while it keeps running."
            ),
            related_points=("InvSt", "Alrm"),
            states=(
                StateGuide(
                    kind=BIT,
                    code=1,
                    label="OVER_TEMP_ALARM",
                    severity=FAULT,
                    message="Battery over-temperature: tripped",
                    probable_causes=("HVAC failure", "Fan failure left unattended"),
                    checks=("Check the container HVAC", "Check FAN_ERROR history"),
                ),
                StateGuide(
                    kind=BIT,
                    code=2,
                    label="OVER_TEMP_WARNING",
                    severity=WARNING,
                    message="Battery warm: derated to about 50 % power",
                    checks=("Check the container HVAC", "Watch for OVER_TEMP_ALARM"),
                ),
                StateGuide(
                    kind=BIT,
                    code=20,
                    label="CONTACTOR_ERROR",
                    severity=FAULT,
                    message="DC contactor didn't close or open as commanded",
                    checks=("Needs a technician: inspect the DC contactor",),
                    safety_note="DC bus may still be live: lock out before opening the cabinet.",
                ),
                StateGuide(
                    kind=BIT,
                    code=21,
                    label="FAN_ERROR",
                    severity=WARNING,
                    message="Cooling fan fault: derated to about 70 % power",
                    probable_causes=("Failed fan", "Clogged air filter"),
                    checks=("See the experience note on bess2 fan errors",),
                ),
                StateGuide(
                    kind=BIT,
                    code=22,
                    label="GROUND_FAULT",
                    severity=FAULT,
                    message="Ground fault on the DC side: tripped",
                    safety_note="Do not reset remotely: a technician must find the fault first.",
                ),
            ),
            updated_at=_AT,
        ),
    ]


def _guides(ids: dict[str, int]) -> list[PointGuide]:
    pv = ids[_PV]
    controller = ids[_PLANT_CONTROLLER]
    return [
        *(guide for name in _BESS for guide in _bess_guides(ids[name])),
        PointGuide(
            site_id=_SITE,
            device_id=pv,
            point_name="InvSt",
            meaning="The PV inverter's operating state (SunSpec 701 InvSt).",
            related_points=("ThrotSrc", "WAvail", "W", "Alrm"),
            states=(
                *_INVERTER_STATES,
                StateGuide(
                    kind=ENUM,
                    code=1,
                    label="SLEEPING",
                    severity=INFO,
                    message="Night: no irradiance",
                ),
            ),
            updated_at=_AT,
        ),
        PointGuide(
            site_id=_SITE,
            device_id=pv,
            point_name="ThrotSrc",
            meaning="Why the PV inverter is producing less than it could (SunSpec 701 ThrotSrc).",
            related_points=("WAvail", "W", "InvSt"),
            states=(
                StateGuide(
                    kind=BIT,
                    code=0,
                    label="MAX_W",
                    severity=INFO,
                    message="At its 5 MW AC rating: clipping",
                    meaning="Normal on clear days with a 1.3 DC/AC ratio.",
                ),
                StateGuide(
                    kind=BIT,
                    code=1,
                    label="FIXED_W",
                    severity=INFO,
                    message="Curtailed by the plant controller's power limit",
                    checks=("Compare W with the plant controller's PV limit",),
                ),
                StateGuide(
                    kind=BIT,
                    code=14,
                    label="DERATED",
                    severity=WARNING,
                    message="Derated by the inverter itself (temperature or hardware)",
                    probable_causes=("Inverter over-temperature", "Blown string fuse"),
                    checks=("Read Alrm for OVER_TEMP or BLOWN_STRING_FUSE",),
                ),
            ),
            updated_at=_AT,
        ),
        PointGuide(
            site_id=_SITE,
            device_id=pv,
            point_name="WAvail",
            meaning="What the array could deliver now at AC, before any curtailment (kW).",
            unit_note="Up to 5,000 kW (the AC rating).",
            related_points=("W", "ThrotSrc"),
            updated_at=_AT,
        ),
        PointGuide(
            site_id=_SITE,
            device_id=controller,
            point_name="GridMode",
            meaning="Whether the site is connected to the utility at the POI.",
            related_points=("Alrm",),
            states=(
                StateGuide(
                    kind=ENUM,
                    code=0,
                    label="GRID_TIED",
                    severity=INFO,
                    message="Connected to the utility: normal",
                ),
                StateGuide(
                    kind=ENUM,
                    code=3,
                    label="BLACKOUT",
                    severity=FAULT,
                    message="Utility lost or POI breaker open: the whole site is de-energised",
                    meaning="This site does not island: every inverter stops without the grid.",
                    checks=(
                        "Is the POI breaker open?",
                        "Call the utility to confirm a feeder outage",
                    ),
                ),
            ),
            updated_at=_AT,
        ),
        PointGuide(
            site_id=_SITE,
            device_id=controller,
            point_name="Alrm",
            meaning="Plant controller alarms.",
            states=(
                StateGuide(
                    kind=BIT,
                    code=0,
                    label="DEVICE_COMM_LOSS",
                    severity=FAULT,
                    message="The controller lost a device: its values are frozen",
                    checks=("Which device's readings stopped changing?",),
                ),
                StateGuide(
                    kind=BIT,
                    code=2,
                    label="POI_METER_FAIL",
                    severity=FAULT,
                    message="POI meter failed: site power control is blind",
                ),
                StateGuide(
                    kind=BIT,
                    code=4,
                    label="EXPORT_LIMIT_ACTIVE",
                    severity=INFO,
                    message="The controller is holding export at its limit (curtailing PV)",
                ),
            ),
            updated_at=_AT,
        ),
        PointGuide(
            site_id=_SITE,
            device_id=ids[_POI_METER],
            point_name="Hz",
            meaning="Grid frequency at the POI.",
            normal_range=NormalRange(min=59.95, max=60.05, note="60 Hz nominal"),
            limits=(
                LimitGuide(
                    condition=LimitCondition.BELOW,
                    value=59.3,
                    severity=FAULT,
                    message="Under-frequency: inverters trip under IEEE 1547",
                ),
                LimitGuide(
                    condition=LimitCondition.ABOVE,
                    value=60.5,
                    severity=FAULT,
                    message="Over-frequency: inverters trip under IEEE 1547",
                ),
            ),
            updated_at=_AT,
        ),
    ]


# --- documents ------------------------------------------------------------------------------------


def _documents(ids: dict[str, int]) -> list[KnowledgeDocument]:
    return [
        KnowledgeDocument(
            document_id=DOC_BESS_MANUAL,
            site_id=_SITE,
            kind=KnowledgeKind.MANUAL,
            title="BESS operating manual (summary)",
            body=(
                "## Operating limits\n"
                "- 2.5 MW charge and discharge, 2.75 MVA inverter, 10 MWh per unit.\n"
                "- SoC is kept within 5-95 %; the inverter goes THROTTLED near either limit.\n"
                "- Ramp limit 500 kW/s: a step setpoint shows THROTTLED for a few seconds.\n"
                "## Faults and warnings\n"
                "- *_ALARM bits trip the unit (InvSt FAULT); they latch until an alarm reset.\n"
                "- *_WARNING bits derate it and clear by themselves: over-temperature warning to "
                "about 50 % power, fan error to about 70 %.\n"
                "## Efficiency\n"
                "- Design round-trip efficiency about 90 % AC to AC (95 % each way), before the "
                "15 kW auxiliary load. Below 85 % over a week, investigate."
            ),
            updated_at=_AT,
        ),
        KnowledgeDocument(
            document_id=DOC_BESS_RESET_SCRIPT,
            site_id=_SITE,
            kind=KnowledgeKind.IM_SCRIPT,
            title="BESS fault: reset and restart",
            body=(
                "1. Read InvSt, Alrm and Evt1 on the tripped unit and note the bits.\n"
                "2. If GROUND_FAULT, CABINET_OPEN, MANUAL_SHUTDOWN or CONTACTOR_ERROR is set: "
                "stop. "
                "Call the site technician; no remote reset.\n"
                "3. Otherwise check the cause is gone (e.g. temperature back to normal).\n"
                "4. Send one alarm reset from the plant controller.\n"
                "5. Expect InvSt STANDBY, then RUNNING once a setpoint is given.\n"
                "6. If it trips again within an hour, don't reset again: open a ticket."
            ),
            device_id=None,
            updated_at=_AT,
        ),
        KnowledgeDocument(
            document_id=DOC_PV_CURTAILMENT_PROCEDURE,
            site_id=_SITE,
            kind=KnowledgeKind.PROCEDURE,
            title="Low PV output: curtailment, clipping or a real loss?",
            body=(
                "1. Compare W with WAvail on pv1.\n"
                "2. W close to WAvail: no loss. If both sit at 5,000 kW, it is clipping (normal).\n"
                "3. W well below WAvail: read ThrotSrc. FIXED_W or EXPORT_LIMIT_ACTIVE on the "
                "plant controller = curtailment by command (normal).\n"
                "4. DERATED set: read Alrm for OVER_TEMP or BLOWN_STRING_FUSE; a blown fuse costs "
                "about 10 % of available power until replaced.\n"
                "5. No bit explains it for more than 15 minutes in daylight: raise it as "
                "underperformance."
            ),
            device_id=ids[_PV],
            updated_at=_AT,
        ),
        KnowledgeDocument(
            document_id=DOC_FAN_NOTE,
            site_id=_SITE,
            kind=KnowledgeKind.EXPERIENCE_NOTE,
            title="bess2 fan errors on hot afternoons",
            body=(
                "bess2 has shown FAN_ERROR a few times on hot afternoons while charging at full "
                "power. Each time the air filter was clogged; cleaning it cleared the warning. "
                "While FAN_ERROR is set the unit runs at about 70 % power, so the afternoon charge "
                "takes longer. Check the filter before replacing the fan."
            ),
            device_id=ids[_BESS[1]],
            point_names=("Evt1",),
            updated_at=_AT,
        ),
    ]


# --- site prompts ---------------------------------------------------------------------------------


def _prompts(ids: dict[str, int]) -> list[SitePrompt]:
    bess1, bess2 = (ids[name] for name in _BESS)
    pv = ids[_PV]
    return [
        # No links: general context.
        SitePrompt(
            prompt_id="seed-2bess-1pv-overview",
            site_id=_SITE,
            name="Site overview",
            text=(
                "A simulated grid-connected hybrid site on a 12.47 kV, 60 Hz utility feeder: one "
                "5 MW PV plant (pv1) and two 2.5 MW / 10 MWh batteries (bess1, bess2), each behind "
                "its own step-up transformer, plus a site load on the POI bus. The POI meter "
                "measures what the site exchanges with the utility (positive = export). The site "
                "cannot island: without the grid everything stops. Answer in site local time."
            ),
            position=1,
            updated_at=_AT,
        ),
        # Points, device ratings and functions together.
        SitePrompt(
            prompt_id="seed-2bess-1pv-battery-operation",
            site_id=_SITE,
            name="How the batteries are operated",
            text=(
                "The batteries charge from PV around midday and discharge into the evening peak. "
                "Keep SoC between 5 and 95 %; THROTTLED near those limits is normal. When asked "
                "about battery health or efficiency, use the round-trip efficiency functions and "
                "compare with the 90 % design value in the ratings."
            ),
            position=2,
            links=SitePromptLinks(
                points=(
                    PromptPointLink(device_id=bess1, point_name="SoC"),
                    PromptPointLink(device_id=bess2, point_name="SoC"),
                    PromptPointLink(device_id=bess1, point_name="InvSt"),
                    PromptPointLink(device_id=bess2, point_name="InvSt"),
                ),
                functions=(
                    "site-bess1-round-trip-efficiency",
                    "site-bess2-round-trip-efficiency",
                ),
                devices=(bess1, bess2),
            ),
            updated_at=_AT,
        ),
        # Documents only.
        SitePrompt(
            prompt_id="seed-2bess-1pv-bess-trips",
            site_id=_SITE,
            name="When a battery trips",
            text=(
                "For a battery fault, walk the engineer through the reset script step by step and "
                "check the experience notes first: some warnings have a known, simple cause. "
                "Never suggest a remote reset for a ground fault, an open door or an emergency "
                "stop."
            ),
            position=3,
            links=SitePromptLinks(
                documents=(DOC_BESS_RESET_SCRIPT, DOC_FAN_NOTE, DOC_BESS_MANUAL),
            ),
            updated_at=_AT,
        ),
        # Points, a document, ratings and a function together.
        SitePrompt(
            prompt_id="seed-2bess-1pv-pv-output",
            site_id=_SITE,
            name="PV output questions",
            text=(
                "Low PV output is usually curtailment or clipping, not a fault. Before calling it "
                "a loss, compare W with WAvail and read ThrotSrc, following the curtailment "
                "procedure. Flat output at 5,000 kW on a clear day is clipping."
            ),
            position=4,
            links=SitePromptLinks(
                points=(
                    PromptPointLink(device_id=pv, point_name="W"),
                    PromptPointLink(device_id=pv, point_name="WAvail"),
                    PromptPointLink(device_id=pv, point_name="ThrotSrc"),
                ),
                functions=("site-assets-active-power",),
                documents=(DOC_PV_CURTAILMENT_PROCEDURE,),
                devices=(pv,),
            ),
            updated_at=_AT,
        ),
        # Points only.
        SitePrompt(
            prompt_id="seed-2bess-1pv-grid",
            site_id=_SITE,
            name="Grid connection",
            text=(
                "For grid questions start from the plant controller's GridMode and the POI "
                "meter's frequency. BLACKOUT means the utility or the POI breaker is out and the "
                "whole site is down, so individual inverter faults at that moment are a "
                "consequence, not the cause."
            ),
            position=5,
            links=SitePromptLinks(
                points=(
                    PromptPointLink(device_id=ids[_PLANT_CONTROLLER], point_name="GridMode"),
                    PromptPointLink(device_id=ids[_POI_METER], point_name="Hz"),
                ),
            ),
            updated_at=_AT,
        ),
    ]


def powerflow_2bess_1pv_knowledge(catalog: SiteCatalog) -> SiteKnowledge:
    """The seed knowledge for this site, with device ids from its approved profile."""
    ids = _device_ids(catalog)
    return SiteKnowledge(
        point_guides=tuple(_guides(ids)),
        documents=tuple(_documents(ids)),
        device_facts=tuple(_facts(ids)),
        site_prompts=tuple(_prompts(ids)),
    )
