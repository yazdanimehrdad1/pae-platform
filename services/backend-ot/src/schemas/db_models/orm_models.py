"""
SQLAlchemy ORM models for database tables.

These models represent the database schema and are used for ORM operations.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from schemas.api_models.alarms import UserAlarmRule
from schemas.api_models.single_line_diagram import SiteSld
from schemas.api_models.virtual_points import VirtualDefinition
from schemas.db_models.column_types import (
    AlarmRuleJSON,
    ReportCadenceJSON,
    ReportDefinitionJSON,
    ReportSnapshotJSON,
    ReportWindowJSON,
    SiteSldJSON,
    VirtualDefinitionJSON,
)
from schemas.reports.definition import ReportDefinition, ReportWindow
from schemas.reports.schedules import ReportCadence
from schemas.reports.snapshot import ReportSnapshot


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass



class Site(Base):
    """
    SQLAlchemy model for the sites table.

    Represents a site/location where devices are deployed.
    """
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Primary key, 4-digit site ID"
    )

    client_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Client identifier"
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Site name (must be unique)"
    )

    location: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Site location as JSON: {street: str, city: str, zip_code: int}"
    )

    operator: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Site operator"
    )

    capacity: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Site capacity"
    )

    device_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of devices at this site (denormalized for performance)"
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional site description"
    )

    coordinates: Mapped[dict[str, float] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Geographic coordinates as JSON: {lat: float, lng: float, elevation_m?: float}"
    )

    profile: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        comment="Site profile key (a package under src/site_profiles/individual_sites/), unique per site; NULL means no site-specific code"
    )

    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="UTC",
        comment="IANA time zone of the site (e.g. America/Los_Angeles), stored canonical; local days and report schedules resolve in it"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when site record was created"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when site record was last updated"
    )

    last_update: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp of last update (synced from external source)"
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Set when soft-deleted; NULL means active"
    )

    def __repr__(self) -> str:
        return f"<Site(id={self.id}, name='{self.name}', location='{self.location}')>"


class Device(Base):
    """
    SQLAlchemy model for the devices table.

    Represents a Modbus device configuration.
    """
    __tablename__ = "devices"

    device_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Primary key, auto-incrementing"
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Device name (must be unique per site)"
    )

    host: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Device hostname or IP address"
    )

    port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=502,
        comment="Device port (default: 502)"
    )

    timeout: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Optional timeout (seconds)"
    )

    site_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Site ID (required)"
    )

    server_address: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Server address"
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional device description"
    )

    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Device type"
    )

    protocol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Modbus",
        server_default="Modbus",
        comment="Communication protocol (Modbus or DNP)"
    )

    vendor: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Device vendor"
    )

    model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Device model"
    )

    scan_ranges: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Auto-computed (or manually locked) scan ranges keyed by register type"
    )

    scan_ranges_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="When True, point CRUD does not overwrite scan_ranges"
    )

    modbus_address_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="zero_based",
        server_default="zero_based",
        comment="zero_based: address sent as-is; one_based: subtract 1 before sending to pymodbus"
    )

    # Polling configuration
    poll_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether polling is enabled for this device"
    )

    read_from_aggregator: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this device reads data from the edge aggregator"
    )

    # configs stored in configs table

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when device record was created"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when device record was last updated"
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Set when soft-deleted; NULL means active"
    )

    __table_args__ = (
        UniqueConstraint('name', 'site_id', name='uq_devices_name_site_id'),
    )

    # Relationship to DevicePointsReading
    device_points_readings: Mapped[list["DevicePointsReading"]] = relationship(
        "DevicePointsReading",
        back_populates="device",
        cascade="all, delete-orphan",
        primaryjoin="Device.device_id == foreign(DevicePointsReading.device_id)"
    )

    def __repr__(self) -> str:
        return f"<Device(device_id={self.device_id}, name='{self.name}', host='{self.host}:{self.port}')>"



class DevicePointsReading(Base):
    """
    SQLAlchemy model for the device_points_readings table.

    Represents a time-series data point reading for a device point.
    Uses composite primary key (timestamp, device_point_id).
    """
    __tablename__ = "device_points_readings"

    __table_args__ = (
        UniqueConstraint(
            'device_point_id',
            'timestamp',
            name='uq_device_points_readings_point_time'
        ),
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        comment="Timestamp when the reading was taken (UTC)"
    )

    site_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Site ID (denormalized from device_points)"
    )

    device_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Device ID (denormalized from device_points)"
    )

    device_point_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("device_points.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        comment="Foreign key to device_points table"
    )

    derived_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="The derived/calculated value (for bitfields, enums, scaled values)"
    )

    # Relationship to DevicePoint
    device_point: Mapped["DevicePoint"] = relationship("DevicePoint", back_populates="readings")
    device: Mapped["Device"] = relationship("Device", back_populates="device_points_readings")

    def __repr__(self) -> str:
        return (
            f"<DevicePointsReading(timestamp={self.timestamp}, site_id={self.site_id}, "
            f"device_id={self.device_id}, device_point_id={self.device_point_id}, "
            f"derived_value={self.derived_value})>"
        )


class DevicePoint(Base):
    """
    SQLAlchemy model for the device_points table.

    Represents a flattened point definition for a device.
    """
    __tablename__ = "device_points"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Primary key"
    )

    site_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Site ID"
    )

    device_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Device ID"
    )

    address: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Point address"
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Point name (must be unique per device)"
    )

    size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Point size"
    )

    data_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Data type"
    )

    scale_factor: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Scale factor"
    )

    unit: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Unit"
    )

    enum_detail: Mapped[dict[str, str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Enum detail mapping"
    )

    bitfield_detail: Mapped[dict[str, str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Bitfield detail mapping"
    )

    byte_order: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="big-endian",
        server_default="big-endian",
        comment="Byte order for interpretation (e.g., big-endian, little-endian)"
    )

    word_order: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="msw_first",
        server_default="msw_first",
        comment="Word order for multi-register types: msw_first or lsw_first"
    )

    poll_kind: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Register type: holding, input, or coils (required for NATIVE points)"
    )

    category: Mapped[str] = mapped_column(
        SAEnum("NATIVE", "STANDARDIZED", "VIRTUAL", name="device_point_category"),
        nullable=False,
        default="NATIVE",
        server_default="NATIVE",
        comment="Point type: NATIVE (by device), STANDARDIZED, or VIRTUAL"
    )

    # DB column "class"; `class` is a Python keyword, so the attribute is point_class.
    point_class: Mapped[str | None] = mapped_column(
        "class",
        String(16),
        nullable=True,
        comment="Optional signal class: ANALOG, BINARY, ALARM or CONTROL"
    )

    severity: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="Optional severity: HIGH, MEDIUM or LOW"
    )

    # VIRTUAL points only. Stored as JSON, loaded as the parsed definition model.
    virtual_definition: Mapped[VirtualDefinition | None] = mapped_column(
        VirtualDefinitionJSON,
        nullable=True,
        comment="VIRTUAL points only: the condition or calculation its values are computed from, on read"
    )

    # STANDARDIZED points only; set through PUT .../{point_id}/link (helpers.device_points.standardized_point_links).
    source_point_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("device_points.id", ondelete="SET NULL"),
        nullable=True,
        comment="STANDARDIZED points only: the NATIVE point on the same device whose readings it shows"
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Set when soft-deleted; NULL means active"
    )

    # Table-level constraints
    __table_args__ = (
        UniqueConstraint('site_id', 'device_id', 'name', name='uq_device_point_site_device_name'),
    )

    # Note: Unique constraint on (device_id, name) is enforced logic-side or via separate constraint
    # We avoid strict DB constraint here to allow logic-side custom error handling as requested,
    # OR we can add it. User asked to check manually.

    # Relationship to DevicePointsReading
    readings: Mapped[list["DevicePointsReading"]] = relationship(
        "DevicePointsReading",
        back_populates="device_point",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DevicePoint(id={self.id}, name='{self.name}', device_id={self.device_id})>"


class AlarmDefinition(Base):
    """An alarm of a site: USER (built in the UI, with a rule) or PROFILE (declared in site_profiles code)."""

    __tablename__ = "alarm_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, comment="USER or PROFILE")
    profile_alarm_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, comment="threshold, comms_stale, condition or profile")
    # USER only. Stored as JSON, loaded as the parsed rule model.
    rule: Mapped[UserAlarmRule | None] = mapped_column(AlarmRuleJSON, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    notify_mobile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    notify_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    def __repr__(self) -> str:
        return f"<AlarmDefinition(id={self.id}, site_id={self.site_id}, name='{self.name}', source={self.source})>"


class AlarmEvent(Base):
    """One raise of an alarm and its clear (cleared_at None while active)."""

    __tablename__ = "alarm_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alarm_definitions.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("devices.device_id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    value_at_raise: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")


class AlarmEvaluationState(Base):
    """The evaluation job's memory between runs, per alarm (the raise and clear delay timers)."""

    __tablename__ = "alarm_evaluation_state"

    definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alarm_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    condition_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clear_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SiteSldRecord(Base):
    """A site's single line diagram: one validated SiteSld document per site."""

    __tablename__ = "site_slds"

    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True)
    # Stored as JSON, loaded as the parsed SiteSld (None only if a stored value no longer parses).
    document: Mapped[SiteSld | None] = mapped_column(SiteSldJSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<SiteSldRecord(site_id={self.site_id}, revision={self.revision})>"


class PvArrayConfigRecord(Base):
    """The PV array behind a PV or INVERTER device: orientation, ratings and losses."""

    __tablename__ = "pv_array_configs"

    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.device_id", ondelete="CASCADE"), primary_key=True
    )
    tilt_deg: Mapped[float] = mapped_column(Float, nullable=False)
    azimuth_deg: Mapped[float] = mapped_column(Float, nullable=False)
    dc_capacity_kw: Mapped[float] = mapped_column(Float, nullable=False)
    ac_capacity_kw: Mapped[float] = mapped_column(Float, nullable=False)
    system_loss_pct: Mapped[float] = mapped_column(Float, nullable=False, server_default="14")
    temp_coefficient_pct_per_c: Mapped[float] = mapped_column(Float, nullable=False, server_default="-0.35")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<PvArrayConfigRecord(device_id={self.device_id})>"


class ReportTemplate(Base):
    """A report template of a site: a named ReportDefinition (window + blocks)."""

    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # Stored as JSON, loaded as the parsed ReportDefinition (None only if a stored value no longer parses).
    definition: Mapped[ReportDefinition | None] = mapped_column(ReportDefinitionJSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReportRun(Base):
    """One report: queued, being generated, generated (with its stored result) or failed."""

    __tablename__ = "report_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("report_templates.id", ondelete="SET NULL"), nullable=True
    )
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("report_schedules.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    definition: Mapped[ReportDefinition | None] = mapped_column(ReportDefinitionJSON, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", server_default="queued")
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="manual", server_default="manual")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[ReportSnapshot | None] = mapped_column(ReportSnapshotJSON, nullable=True)


class ReportSchedule(Base):
    """Generate a template's report on a cadence (site time), keeping only some of those reports."""

    __tablename__ = "report_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("report_templates.id", ondelete="CASCADE"), nullable=False)
    # Stored as JSON, loaded as the parsed model (None only if a stored value no longer parses).
    cadence: Mapped[ReportCadence | None] = mapped_column(ReportCadenceJSON, nullable=False)
    window_override: Mapped[ReportWindow | None] = mapped_column(ReportWindowJSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    keep_last: Mapped[int | None] = mapped_column(Integer, nullable=True)
    keep_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
