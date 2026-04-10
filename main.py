"""
AH Collector - Auction House Collector Application
Flask backend providing REST API and serving the frontend.
Also includes an AI-driven controller for BESS/solar, Bitcoin mining, and cooling systems.
"""

import os
import json
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, func

app = Flask(__name__)

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "ah_collector.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────

class Item(db.Model):
    """Represents an auction house item being tracked."""

    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False, default="Uncategorized")
    current_price = db.Column(db.Float, nullable=False, default=0.0)
    min_price = db.Column(db.Float, nullable=True)
    max_price = db.Column(db.Float, nullable=True)
    collection = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_watchlisted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    price_history = db.relationship(
        "PriceHistory", backref="item", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "current_price": self.current_price,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "collection": self.collection,
            "notes": self.notes,
            "is_watchlisted": self.is_watchlisted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PriceHistory(db.Model):
    """Records price changes for tracked items."""

    __tablename__ = "price_history"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    price = db.Column(db.Float, nullable=False)
    recorded_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "price": self.price,
            "recorded_at": (
                self.recorded_at.isoformat() if self.recorded_at else None
            ),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Energy / Mining / AI Models
# ──────────────────────────────────────────────────────────────────────────────

class SolarFarm(db.Model):
    """Solar farm configuration and live telemetry."""

    __tablename__ = "solar_farms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    capacity_kw = db.Column(db.Float, nullable=False, default=0.0)
    panel_count = db.Column(db.Integer, default=0)
    location = db.Column(db.String(200), nullable=True)
    # Live telemetry
    current_output_kw = db.Column(db.Float, default=0.0)
    irradiance_wm2 = db.Column(db.Float, default=0.0)
    efficiency_pct = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "capacity_kw": self.capacity_kw,
            "panel_count": self.panel_count,
            "location": self.location,
            "current_output_kw": self.current_output_kw,
            "irradiance_wm2": self.irradiance_wm2,
            "efficiency_pct": self.efficiency_pct,
            "is_active": self.is_active,
            "utilization_pct": round(
                (self.current_output_kw / self.capacity_kw * 100)
                if self.capacity_kw > 0 else 0, 1
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BessUnit(db.Model):
    """Battery Energy Storage System unit."""

    __tablename__ = "bess_units"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    capacity_kwh = db.Column(db.Float, nullable=False, default=0.0)
    max_charge_rate_kw = db.Column(db.Float, default=0.0)
    max_discharge_rate_kw = db.Column(db.Float, default=0.0)
    # Live state – positive current_power_kw = charging, negative = discharging
    state_of_charge_pct = db.Column(db.Float, default=0.0)
    current_power_kw = db.Column(db.Float, default=0.0)
    temperature_c = db.Column(db.Float, default=25.0)
    is_active = db.Column(db.Boolean, default=True)
    # Health metrics
    cycle_count = db.Column(db.Integer, default=0)
    health_pct = db.Column(db.Float, default=100.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        if self.current_power_kw > 0:
            status = "charging"
        elif self.current_power_kw < 0:
            status = "discharging"
        else:
            status = "idle"
        return {
            "id": self.id,
            "name": self.name,
            "capacity_kwh": self.capacity_kwh,
            "max_charge_rate_kw": self.max_charge_rate_kw,
            "max_discharge_rate_kw": self.max_discharge_rate_kw,
            "state_of_charge_pct": self.state_of_charge_pct,
            "current_power_kw": self.current_power_kw,
            "temperature_c": self.temperature_c,
            "is_active": self.is_active,
            "cycle_count": self.cycle_count,
            "health_pct": self.health_pct,
            "stored_energy_kwh": round(
                self.capacity_kwh * self.state_of_charge_pct / 100, 2
            ),
            "status": status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MiningRig(db.Model):
    """Bitcoin mining rig with performance and power metrics."""

    __tablename__ = "mining_rigs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    model = db.Column(db.String(200), nullable=True)
    # Hardware specifications
    max_hash_rate_ths = db.Column(db.Float, default=0.0)
    max_power_w = db.Column(db.Float, default=0.0)
    # Live operational state
    is_active = db.Column(db.Boolean, default=False)
    throttle_pct = db.Column(db.Float, default=100.0)
    current_hash_rate_ths = db.Column(db.Float, default=0.0)
    current_power_w = db.Column(db.Float, default=0.0)
    # Performance counters
    accepted_shares = db.Column(db.Integer, default=0)
    rejected_shares = db.Column(db.Integer, default=0)
    uptime_hours = db.Column(db.Float, default=0.0)
    # Thermal
    chip_temp_c = db.Column(db.Float, default=0.0)
    ambient_temp_c = db.Column(db.Float, default=25.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        efficiency = (
            round(self.current_hash_rate_ths / (self.current_power_w / 1000), 4)
            if self.current_power_w > 0 else 0
        )
        return {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "max_hash_rate_ths": self.max_hash_rate_ths,
            "max_power_w": self.max_power_w,
            "is_active": self.is_active,
            "throttle_pct": self.throttle_pct,
            "current_hash_rate_ths": self.current_hash_rate_ths,
            "current_power_w": self.current_power_w,
            "accepted_shares": self.accepted_shares,
            "rejected_shares": self.rejected_shares,
            "uptime_hours": self.uptime_hours,
            "chip_temp_c": self.chip_temp_c,
            "ambient_temp_c": self.ambient_temp_c,
            "efficiency_ths_per_kw": efficiency,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CoolingZone(db.Model):
    """Cooling system zone (CRAC, chiller, immersion cooling, etc.)."""

    __tablename__ = "cooling_zones"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    # Zone types: CRAC, CHILLER, FAN, IMMERSION
    zone_type = db.Column(db.String(50), default="CRAC")
    capacity_kw = db.Column(db.Float, default=0.0)
    # Setpoints and limits
    setpoint_temp_c = db.Column(db.Float, default=22.0)
    max_temp_c = db.Column(db.Float, default=30.0)
    min_temp_c = db.Column(db.Float, default=18.0)
    # Live state
    is_active = db.Column(db.Boolean, default=True)
    current_power_kw = db.Column(db.Float, default=0.0)
    current_temp_c = db.Column(db.Float, default=22.0)
    fan_speed_pct = db.Column(db.Float, default=50.0)
    coolant_flow_lpm = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        if self.current_temp_c <= self.setpoint_temp_c + 2:
            temp_status = "ok"
        elif self.current_temp_c <= self.max_temp_c:
            temp_status = "warning"
        else:
            temp_status = "critical"
        return {
            "id": self.id,
            "name": self.name,
            "zone_type": self.zone_type,
            "capacity_kw": self.capacity_kw,
            "setpoint_temp_c": self.setpoint_temp_c,
            "max_temp_c": self.max_temp_c,
            "min_temp_c": self.min_temp_c,
            "is_active": self.is_active,
            "current_power_kw": self.current_power_kw,
            "current_temp_c": self.current_temp_c,
            "fan_speed_pct": self.fan_speed_pct,
            "coolant_flow_lpm": self.coolant_flow_lpm,
            "temp_status": temp_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AIAction(db.Model):
    """Log of AI controller recommendations and executed actions."""

    __tablename__ = "ai_actions"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    action_type = db.Column(db.String(50), nullable=False)
    target_system = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    target_name = db.Column(db.String(200), nullable=True)
    parameter = db.Column(db.String(100), nullable=True)
    old_value = db.Column(db.Float, nullable=True)
    new_value = db.Column(db.Float, nullable=True)
    reason = db.Column(db.Text, nullable=True)
    confidence_score = db.Column(db.Float, default=1.0)
    was_executed = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "action_type": self.action_type,
            "target_system": self.target_system,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "parameter": self.parameter,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "confidence_score": self.confidence_score,
            "was_executed": self.was_executed,
        }


# ──────────────────────────────────────────────────────────────────────────────
# AI Energy Controller
# ──────────────────────────────────────────────────────────────────────────────

class EnergyAIController:
    """
    AI controller for optimizing BESS, solar farm, Bitcoin mining, and cooling.

    Decision priority:
      1. Safety  – over-temperature shutdowns and battery thermal protection
      2. Cooling – maintain target zone temperatures
      3. Energy  – maximise mining yield from available solar / stored energy
    """

    # ── Temperature thresholds (°C) ──────────────────────────────────────────
    CHIP_TEMP_WARNING   = 75.0
    CHIP_TEMP_CRITICAL  = 85.0
    CHIP_TEMP_EMERGENCY = 90.0
    BESS_TEMP_MAX       = 45.0

    # ── Battery SOC thresholds (%) ───────────────────────────────────────────
    BESS_SOC_MIN  = 15.0   # Stop discharging below this
    BESS_SOC_LOW  = 25.0   # Start reducing mining to protect battery
    BESS_SOC_HIGH = 85.0   # Battery well-charged – allow increased mining
    BESS_SOC_MAX  = 95.0   # Stop charging above this

    # ── Throttle step sizes (%) ──────────────────────────────────────────────
    THROTTLE_STEP = 10.0
    MIN_THROTTLE  = 10.0
    MAX_THROTTLE  = 100.0

    # ── Minimum meaningful power change to avoid noise (kW) ─────────────────
    POWER_DEAD_BAND = 0.5

    def _get_system_state(self):
        """Collect current telemetry from all active subsystems."""
        solar_farms   = SolarFarm.query.filter_by(is_active=True).all()
        bess_units    = BessUnit.query.filter_by(is_active=True).all()
        mining_rigs   = MiningRig.query.filter_by(is_active=True).all()
        cooling_zones = CoolingZone.query.filter_by(is_active=True).all()

        total_solar_kw      = sum(s.current_output_kw for s in solar_farms)
        total_cap_kwh       = sum(b.capacity_kwh for b in bess_units)
        avg_bess_soc        = (
            sum(b.state_of_charge_pct * b.capacity_kwh for b in bess_units) / total_cap_kwh
            if total_cap_kwh > 0 else 0.0
        )
        total_mining_kw     = sum(r.current_power_w / 1000.0 for r in mining_rigs)
        total_cooling_kw    = sum(c.current_power_kw for c in cooling_zones)

        return {
            "solar_farms":    solar_farms,
            "bess_units":     bess_units,
            "mining_rigs":    mining_rigs,
            "cooling_zones":  cooling_zones,
            "total_solar_kw": total_solar_kw,
            "avg_bess_soc":   avg_bess_soc,
            "total_mining_kw":  total_mining_kw,
            "total_cooling_kw": total_cooling_kw,
            "net_power_kw":   total_solar_kw - total_mining_kw - total_cooling_kw,
        }

    def analyze(self):
        """
        Analyse current system state and generate prioritised action
        recommendations.  Returns (state_summary_dict, [recommendation_dict]).
        """
        state = self._get_system_state()
        recs  = []

        # ── Priority 1: Thermal safety for mining rigs ────────────────────
        for rig in state["mining_rigs"]:
            if rig.chip_temp_c >= self.CHIP_TEMP_EMERGENCY:
                recs.append({
                    "action_type":      "EMERGENCY_SHUTDOWN",
                    "target_system":    "MINING",
                    "target_id":        rig.id,
                    "target_name":      rig.name,
                    "parameter":        "is_active",
                    "old_value":        1.0 if rig.is_active else 0.0,
                    "new_value":        0.0,
                    "reason":           (
                        f"EMERGENCY: chip temperature {rig.chip_temp_c}°C "
                        f"exceeds emergency threshold {self.CHIP_TEMP_EMERGENCY}°C"
                    ),
                    "confidence_score": 1.0,
                    "priority":         1,
                })
            elif rig.chip_temp_c >= self.CHIP_TEMP_CRITICAL:
                new_throttle = max(self.MIN_THROTTLE, rig.throttle_pct - self.THROTTLE_STEP * 2)
                recs.append({
                    "action_type":      "REDUCE_THROTTLE",
                    "target_system":    "MINING",
                    "target_id":        rig.id,
                    "target_name":      rig.name,
                    "parameter":        "throttle_pct",
                    "old_value":        rig.throttle_pct,
                    "new_value":        new_throttle,
                    "reason":           (
                        f"Critical chip temperature {rig.chip_temp_c}°C – "
                        f"reducing throttle by 20 %"
                    ),
                    "confidence_score": 0.95,
                    "priority":         1,
                })
            elif rig.chip_temp_c >= self.CHIP_TEMP_WARNING:
                new_throttle = max(self.MIN_THROTTLE, rig.throttle_pct - self.THROTTLE_STEP)
                recs.append({
                    "action_type":      "REDUCE_THROTTLE",
                    "target_system":    "MINING",
                    "target_id":        rig.id,
                    "target_name":      rig.name,
                    "parameter":        "throttle_pct",
                    "old_value":        rig.throttle_pct,
                    "new_value":        new_throttle,
                    "reason":           (
                        f"Temperature warning {rig.chip_temp_c}°C – "
                        f"reducing throttle by 10 %"
                    ),
                    "confidence_score": 0.85,
                    "priority":         1,
                })

        # ── Priority 1: Thermal safety for BESS ──────────────────────────
        for bess in state["bess_units"]:
            if bess.temperature_c >= self.BESS_TEMP_MAX and bess.current_power_kw > 0:
                recs.append({
                    "action_type":      "STOP_CHARGING",
                    "target_system":    "BESS",
                    "target_id":        bess.id,
                    "target_name":      bess.name,
                    "parameter":        "current_power_kw",
                    "old_value":        bess.current_power_kw,
                    "new_value":        0.0,
                    "reason":           (
                        f"Battery temperature {bess.temperature_c}°C "
                        f"exceeds maximum {self.BESS_TEMP_MAX}°C – stopping charge"
                    ),
                    "confidence_score": 1.0,
                    "priority":         1,
                })

        # ── Priority 2: Cooling zone management ──────────────────────────
        for zone in state["cooling_zones"]:
            if zone.current_temp_c > zone.max_temp_c:
                new_speed = min(100.0, zone.fan_speed_pct + 20.0)
                recs.append({
                    "action_type":      "INCREASE_COOLING",
                    "target_system":    "COOLING",
                    "target_id":        zone.id,
                    "target_name":      zone.name,
                    "parameter":        "fan_speed_pct",
                    "old_value":        zone.fan_speed_pct,
                    "new_value":        new_speed,
                    "reason":           (
                        f"Zone temperature {zone.current_temp_c}°C "
                        f"exceeds maximum {zone.max_temp_c}°C"
                    ),
                    "confidence_score": 0.95,
                    "priority":         2,
                })
            elif zone.current_temp_c > zone.setpoint_temp_c + 3:
                new_speed = min(100.0, zone.fan_speed_pct + 10.0)
                recs.append({
                    "action_type":      "INCREASE_COOLING",
                    "target_system":    "COOLING",
                    "target_id":        zone.id,
                    "target_name":      zone.name,
                    "parameter":        "fan_speed_pct",
                    "old_value":        zone.fan_speed_pct,
                    "new_value":        new_speed,
                    "reason":           (
                        f"Zone temperature {zone.current_temp_c}°C is "
                        f"3 °C above setpoint {zone.setpoint_temp_c}°C"
                    ),
                    "confidence_score": 0.80,
                    "priority":         2,
                })
            elif zone.current_temp_c < zone.setpoint_temp_c - 3 and zone.fan_speed_pct > 20:
                new_speed = max(20.0, zone.fan_speed_pct - 10.0)
                recs.append({
                    "action_type":      "REDUCE_COOLING",
                    "target_system":    "COOLING",
                    "target_id":        zone.id,
                    "target_name":      zone.name,
                    "parameter":        "fan_speed_pct",
                    "old_value":        zone.fan_speed_pct,
                    "new_value":        new_speed,
                    "reason":           (
                        f"Zone temperature {zone.current_temp_c}°C is "
                        f"well below setpoint – saving energy"
                    ),
                    "confidence_score": 0.70,
                    "priority":         3,
                })

        # ── Priority 3: Energy balance optimisation ───────────────────────
        net_kw   = state["net_power_kw"]
        avg_soc  = state["avg_bess_soc"]

        if net_kw > self.POWER_DEAD_BAND:
            # Surplus solar – try to store in BESS first
            for bess in state["bess_units"]:
                if (bess.state_of_charge_pct < self.BESS_SOC_MAX
                        and bess.temperature_c < self.BESS_TEMP_MAX):
                    charge_kw = min(net_kw, bess.max_charge_rate_kw)
                    if charge_kw > 0.1 and abs(bess.current_power_kw - charge_kw) > self.POWER_DEAD_BAND:
                        recs.append({
                            "action_type":      "CHARGE_BESS",
                            "target_system":    "BESS",
                            "target_id":        bess.id,
                            "target_name":      bess.name,
                            "parameter":        "current_power_kw",
                            "old_value":        bess.current_power_kw,
                            "new_value":        round(charge_kw, 2),
                            "reason":           (
                                f"Surplus solar power {net_kw:.1f} kW – "
                                f"charging BESS at {charge_kw:.1f} kW"
                            ),
                            "confidence_score": 0.85,
                            "priority":         3,
                        })
                    break

            # If BESS is full, push more power to mining
            if avg_soc >= self.BESS_SOC_HIGH:
                for rig in state["mining_rigs"]:
                    if (rig.is_active
                            and rig.throttle_pct < self.MAX_THROTTLE
                            and rig.chip_temp_c < self.CHIP_TEMP_WARNING):
                        new_throttle = min(self.MAX_THROTTLE, rig.throttle_pct + self.THROTTLE_STEP)
                        recs.append({
                            "action_type":      "INCREASE_THROTTLE",
                            "target_system":    "MINING",
                            "target_id":        rig.id,
                            "target_name":      rig.name,
                            "parameter":        "throttle_pct",
                            "old_value":        rig.throttle_pct,
                            "new_value":        new_throttle,
                            "reason":           (
                                f"BESS SOC {avg_soc:.1f}% and surplus solar "
                                f"{net_kw:.1f} kW – increasing mining yield"
                            ),
                            "confidence_score": 0.75,
                            "priority":         3,
                        })

        elif net_kw < -self.POWER_DEAD_BAND:
            # Power deficit – first try discharging BESS
            deficit = abs(net_kw)
            if avg_soc > self.BESS_SOC_LOW:
                for bess in state["bess_units"]:
                    if bess.state_of_charge_pct > self.BESS_SOC_MIN:
                        discharge_kw = min(deficit, bess.max_discharge_rate_kw)
                        if discharge_kw > 0.1 and abs(bess.current_power_kw + discharge_kw) > self.POWER_DEAD_BAND:
                            recs.append({
                                "action_type":      "DISCHARGE_BESS",
                                "target_system":    "BESS",
                                "target_id":        bess.id,
                                "target_name":      bess.name,
                                "parameter":        "current_power_kw",
                                "old_value":        bess.current_power_kw,
                                "new_value":        round(-discharge_kw, 2),
                                "reason":           (
                                    f"Power deficit {deficit:.1f} kW – "
                                    f"discharging BESS at {discharge_kw:.1f} kW"
                                ),
                                "confidence_score": 0.80,
                                "priority":         3,
                            })
                        break
            else:
                # Battery too low – throttle down miners
                for rig in state["mining_rigs"]:
                    if rig.is_active and rig.throttle_pct > self.MIN_THROTTLE:
                        new_throttle = max(self.MIN_THROTTLE, rig.throttle_pct - self.THROTTLE_STEP)
                        recs.append({
                            "action_type":      "REDUCE_THROTTLE",
                            "target_system":    "MINING",
                            "target_id":        rig.id,
                            "target_name":      rig.name,
                            "parameter":        "throttle_pct",
                            "old_value":        rig.throttle_pct,
                            "new_value":        new_throttle,
                            "reason":           (
                                f"Low battery SOC {avg_soc:.1f}% and power "
                                f"deficit {deficit:.1f} kW – reducing mining load"
                            ),
                            "confidence_score": 0.85,
                            "priority":         3,
                        })

        # Sort by priority then descending confidence
        recs.sort(key=lambda r: (r.get("priority", 9), -r.get("confidence_score", 0)))

        # Persist recommendations as un-executed AIAction records
        saved = []
        for r in recs:
            action = AIAction(
                action_type=r["action_type"],
                target_system=r["target_system"],
                target_id=r.get("target_id"),
                target_name=r.get("target_name"),
                parameter=r.get("parameter"),
                old_value=r.get("old_value"),
                new_value=r.get("new_value"),
                reason=r.get("reason"),
                confidence_score=r.get("confidence_score", 1.0),
                was_executed=False,
            )
            db.session.add(action)
            db.session.flush()
            saved.append(action.to_dict())

        db.session.commit()

        summary = {
            "total_solar_kw":   round(state["total_solar_kw"], 2),
            "avg_bess_soc":     round(state["avg_bess_soc"], 1),
            "total_mining_kw":  round(state["total_mining_kw"], 2),
            "total_cooling_kw": round(state["total_cooling_kw"], 2),
            "net_power_kw":     round(state["net_power_kw"], 2),
        }
        return summary, saved

    def execute_actions(self, action_ids):
        """Apply a list of saved AIAction IDs to their target subsystems."""
        executed = []
        for aid in action_ids:
            action = db.session.get(AIAction, aid)
            if not action or action.was_executed:
                continue
            if self._apply_action(action):
                action.was_executed = True
                executed.append(action.id)
        db.session.commit()
        return executed

    def _apply_action(self, action):
        """Write an AIAction's new_value to the target model field."""
        try:
            if action.target_system == "MINING" and action.target_id:
                rig = db.session.get(MiningRig, action.target_id)
                if not rig:
                    return False
                if action.action_type == "EMERGENCY_SHUTDOWN":
                    rig.is_active = False
                    rig.throttle_pct = 0.0
                    rig.current_hash_rate_ths = 0.0
                    rig.current_power_w = 0.0
                elif action.action_type in ("REDUCE_THROTTLE", "INCREASE_THROTTLE"):
                    rig.throttle_pct = action.new_value
                    rig.current_hash_rate_ths = rig.max_hash_rate_ths * rig.throttle_pct / 100.0
                    rig.current_power_w = rig.max_power_w * rig.throttle_pct / 100.0
                rig.updated_at = datetime.now(timezone.utc)

            elif action.target_system == "BESS" and action.target_id:
                bess = db.session.get(BessUnit, action.target_id)
                if not bess:
                    return False
                if action.action_type in ("CHARGE_BESS", "DISCHARGE_BESS", "STOP_CHARGING"):
                    bess.current_power_kw = action.new_value
                bess.updated_at = datetime.now(timezone.utc)

            elif action.target_system == "COOLING" and action.target_id:
                zone = db.session.get(CoolingZone, action.target_id)
                if not zone:
                    return False
                if action.action_type in ("INCREASE_COOLING", "REDUCE_COOLING"):
                    zone.fan_speed_pct = action.new_value
                    # Fan power scales roughly as the cube of speed
                    zone.current_power_kw = round(
                        zone.capacity_kw * (zone.fan_speed_pct / 100.0) ** 3, 3
                    )
                zone.updated_at = datetime.now(timezone.utc)

            return True
        except Exception:
            return False


_ai_controller = EnergyAIController()


# ──────────────────────────────────────────────────────────────────────────────
# Frontend routes
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main dashboard."""
    return render_template("index.html")


# ──────────────────────────────────────────────────────────────────────────────
# API routes
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/items", methods=["GET"])
def get_items():
    """Return all tracked items, with optional search/filter."""
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    watchlisted = request.args.get("watchlisted", "").strip().lower()

    query = Item.query

    if search:
        query = query.filter(
            Item.name.ilike(f"%{search}%") | Item.collection.ilike(f"%{search}%")
        )
    if category:
        query = query.filter(Item.category.ilike(f"%{category}%"))
    if watchlisted == "true":
        query = query.filter(Item.is_watchlisted.is_(True))

    items = query.order_by(desc(Item.updated_at)).all()
    return jsonify([item.to_dict() for item in items])


@app.route("/api/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    """Return a single item with its price history."""
    item = db.get_or_404(Item, item_id)
    data = item.to_dict()
    data["price_history"] = [
        ph.to_dict()
        for ph in PriceHistory.query.filter_by(item_id=item_id)
        .order_by(PriceHistory.recorded_at)
        .all()
    ]
    return jsonify(data)


@app.route("/api/items", methods=["POST"])
def create_item():
    """Create a new tracked item."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    name = payload.get("name", "").strip()
    if not name:
        abort(400, description="'name' is required.")

    price = payload.get("current_price", 0.0)
    try:
        price = float(price)
    except (TypeError, ValueError):
        abort(400, description="'current_price' must be a number.")

    item = Item(
        name=name,
        category=payload.get("category", "Uncategorized"),
        current_price=price,
        min_price=payload.get("min_price"),
        max_price=payload.get("max_price"),
        collection=payload.get("collection"),
        notes=payload.get("notes"),
        is_watchlisted=bool(payload.get("is_watchlisted", False)),
    )
    db.session.add(item)
    db.session.flush()  # get item.id before adding price history

    # Record the initial price in history
    ph = PriceHistory(item_id=item.id, price=price)
    db.session.add(ph)
    db.session.commit()

    return jsonify(item.to_dict()), 201


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    """Update an existing item (and record price change if price differs)."""
    item = db.get_or_404(Item, item_id)
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    if "name" in payload:
        name = payload["name"].strip()
        if not name:
            abort(400, description="'name' cannot be empty.")
        item.name = name

    if "category" in payload:
        item.category = payload["category"]
    if "collection" in payload:
        item.collection = payload["collection"]
    if "notes" in payload:
        item.notes = payload["notes"]
    if "is_watchlisted" in payload:
        item.is_watchlisted = bool(payload["is_watchlisted"])
    if "min_price" in payload:
        item.min_price = payload["min_price"]
    if "max_price" in payload:
        item.max_price = payload["max_price"]

    if "current_price" in payload:
        new_price = payload["current_price"]
        try:
            new_price = float(new_price)
        except (TypeError, ValueError):
            abort(400, description="'current_price' must be a number.")

        if new_price != item.current_price:
            ph = PriceHistory(item_id=item.id, price=new_price)
            db.session.add(ph)
            item.current_price = new_price

    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(item.to_dict())


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    """Delete a tracked item."""
    item = db.get_or_404(Item, item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": f"Item {item_id} deleted."})


@app.route("/api/items/<int:item_id>/watchlist", methods=["POST"])
def toggle_watchlist(item_id):
    """Toggle the watchlist status of an item."""
    item = db.get_or_404(Item, item_id)
    item.is_watchlisted = not item.is_watchlisted
    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"is_watchlisted": item.is_watchlisted})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Return summary statistics for the dashboard."""
    total = Item.query.count()
    watchlisted = Item.query.filter_by(is_watchlisted=True).count()

    # Category breakdown
    categories = (
        db.session.query(Item.category, func.count(Item.id))
        .group_by(Item.category)
        .all()
    )
    category_data = [{"category": c, "count": n} for c, n in categories]

    return jsonify(
        {
            "total_items": total,
            "watchlisted_items": watchlisted,
            "categories": category_data,
        }
    )


@app.route("/energy")
def energy_dashboard():
    """Serve the energy / AI control dashboard."""
    return render_template("energy.html")


# ──────────────────────────────────────────────────────────────────────────────
# Solar Farm API
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/solar", methods=["GET"])
def get_solar_farms():
    """Return all solar farms."""
    farms = SolarFarm.query.order_by(SolarFarm.name).all()
    return jsonify([f.to_dict() for f in farms])


@app.route("/api/solar/<int:farm_id>", methods=["GET"])
def get_solar_farm(farm_id):
    """Return a single solar farm."""
    return jsonify(db.get_or_404(SolarFarm, farm_id).to_dict())


@app.route("/api/solar", methods=["POST"])
def create_solar_farm():
    """Create a new solar farm."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")
    name = payload.get("name", "").strip()
    if not name:
        abort(400, description="'name' is required.")
    try:
        capacity_kw = float(payload.get("capacity_kw", 0))
    except (TypeError, ValueError):
        abort(400, description="'capacity_kw' must be a number.")

    farm = SolarFarm(
        name=name,
        capacity_kw=capacity_kw,
        panel_count=int(payload.get("panel_count", 0)),
        location=payload.get("location"),
        current_output_kw=float(payload.get("current_output_kw", 0)),
        irradiance_wm2=float(payload.get("irradiance_wm2", 0)),
        efficiency_pct=float(payload.get("efficiency_pct", 0)),
        is_active=bool(payload.get("is_active", True)),
    )
    db.session.add(farm)
    db.session.commit()
    return jsonify(farm.to_dict()), 201


@app.route("/api/solar/<int:farm_id>", methods=["PUT"])
def update_solar_farm(farm_id):
    """Update solar farm telemetry or configuration."""
    farm = db.get_or_404(SolarFarm, farm_id)
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    for field in ("name", "location"):
        if field in payload:
            farm.__setattr__(field, payload[field])
    for field in ("capacity_kw", "current_output_kw", "irradiance_wm2", "efficiency_pct"):
        if field in payload:
            try:
                farm.__setattr__(field, float(payload[field]))
            except (TypeError, ValueError):
                abort(400, description=f"'{field}' must be a number.")
    if "panel_count" in payload:
        farm.panel_count = int(payload["panel_count"])
    if "is_active" in payload:
        farm.is_active = bool(payload["is_active"])

    farm.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(farm.to_dict())


@app.route("/api/solar/<int:farm_id>", methods=["DELETE"])
def delete_solar_farm(farm_id):
    """Delete a solar farm."""
    farm = db.get_or_404(SolarFarm, farm_id)
    db.session.delete(farm)
    db.session.commit()
    return jsonify({"message": f"Solar farm {farm_id} deleted."})


# ──────────────────────────────────────────────────────────────────────────────
# BESS API
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/bess", methods=["GET"])
def get_bess_units():
    """Return all BESS units."""
    units = BessUnit.query.order_by(BessUnit.name).all()
    return jsonify([u.to_dict() for u in units])


@app.route("/api/bess/<int:unit_id>", methods=["GET"])
def get_bess_unit(unit_id):
    """Return a single BESS unit."""
    return jsonify(db.get_or_404(BessUnit, unit_id).to_dict())


@app.route("/api/bess", methods=["POST"])
def create_bess_unit():
    """Create a new BESS unit."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")
    name = payload.get("name", "").strip()
    if not name:
        abort(400, description="'name' is required.")
    try:
        capacity_kwh = float(payload.get("capacity_kwh", 0))
    except (TypeError, ValueError):
        abort(400, description="'capacity_kwh' must be a number.")

    unit = BessUnit(
        name=name,
        capacity_kwh=capacity_kwh,
        max_charge_rate_kw=float(payload.get("max_charge_rate_kw", 0)),
        max_discharge_rate_kw=float(payload.get("max_discharge_rate_kw", 0)),
        state_of_charge_pct=float(payload.get("state_of_charge_pct", 0)),
        current_power_kw=float(payload.get("current_power_kw", 0)),
        temperature_c=float(payload.get("temperature_c", 25)),
        cycle_count=int(payload.get("cycle_count", 0)),
        health_pct=float(payload.get("health_pct", 100)),
        is_active=bool(payload.get("is_active", True)),
    )
    db.session.add(unit)
    db.session.commit()
    return jsonify(unit.to_dict()), 201


@app.route("/api/bess/<int:unit_id>", methods=["PUT"])
def update_bess_unit(unit_id):
    """Update BESS telemetry or configuration."""
    unit = db.get_or_404(BessUnit, unit_id)
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    for field in ("capacity_kwh", "max_charge_rate_kw", "max_discharge_rate_kw",
                  "state_of_charge_pct", "current_power_kw", "temperature_c", "health_pct"):
        if field in payload:
            try:
                unit.__setattr__(field, float(payload[field]))
            except (TypeError, ValueError):
                abort(400, description=f"'{field}' must be a number.")
    if "name" in payload:
        unit.name = payload["name"]
    if "cycle_count" in payload:
        unit.cycle_count = int(payload["cycle_count"])
    if "is_active" in payload:
        unit.is_active = bool(payload["is_active"])

    unit.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(unit.to_dict())


@app.route("/api/bess/<int:unit_id>", methods=["DELETE"])
def delete_bess_unit(unit_id):
    """Delete a BESS unit."""
    unit = db.get_or_404(BessUnit, unit_id)
    db.session.delete(unit)
    db.session.commit()
    return jsonify({"message": f"BESS unit {unit_id} deleted."})


# ──────────────────────────────────────────────────────────────────────────────
# Mining Rigs API
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/mining/rigs", methods=["GET"])
def get_mining_rigs():
    """Return all mining rigs."""
    rigs = MiningRig.query.order_by(MiningRig.name).all()
    return jsonify([r.to_dict() for r in rigs])


@app.route("/api/mining/rigs/<int:rig_id>", methods=["GET"])
def get_mining_rig(rig_id):
    """Return a single mining rig."""
    return jsonify(db.get_or_404(MiningRig, rig_id).to_dict())


@app.route("/api/mining/rigs", methods=["POST"])
def create_mining_rig():
    """Register a new mining rig."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")
    name = payload.get("name", "").strip()
    if not name:
        abort(400, description="'name' is required.")

    rig = MiningRig(
        name=name,
        model=payload.get("model"),
        max_hash_rate_ths=float(payload.get("max_hash_rate_ths", 0)),
        max_power_w=float(payload.get("max_power_w", 0)),
        is_active=bool(payload.get("is_active", False)),
        throttle_pct=float(payload.get("throttle_pct", 100)),
        current_hash_rate_ths=float(payload.get("current_hash_rate_ths", 0)),
        current_power_w=float(payload.get("current_power_w", 0)),
        accepted_shares=int(payload.get("accepted_shares", 0)),
        rejected_shares=int(payload.get("rejected_shares", 0)),
        uptime_hours=float(payload.get("uptime_hours", 0)),
        chip_temp_c=float(payload.get("chip_temp_c", 0)),
        ambient_temp_c=float(payload.get("ambient_temp_c", 25)),
    )
    db.session.add(rig)
    db.session.commit()
    return jsonify(rig.to_dict()), 201


@app.route("/api/mining/rigs/<int:rig_id>", methods=["PUT"])
def update_mining_rig(rig_id):
    """Update mining rig telemetry or configuration."""
    rig = db.get_or_404(MiningRig, rig_id)
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    if "name" in payload:
        rig.name = payload["name"]
    if "model" in payload:
        rig.model = payload["model"]
    if "is_active" in payload:
        rig.is_active = bool(payload["is_active"])
    for field in ("max_hash_rate_ths", "max_power_w", "throttle_pct",
                  "current_hash_rate_ths", "current_power_w",
                  "chip_temp_c", "ambient_temp_c", "uptime_hours"):
        if field in payload:
            try:
                rig.__setattr__(field, float(payload[field]))
            except (TypeError, ValueError):
                abort(400, description=f"'{field}' must be a number.")
    for field in ("accepted_shares", "rejected_shares"):
        if field in payload:
            rig.__setattr__(field, int(payload[field]))

    rig.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(rig.to_dict())


@app.route("/api/mining/rigs/<int:rig_id>", methods=["DELETE"])
def delete_mining_rig(rig_id):
    """Remove a mining rig."""
    rig = db.get_or_404(MiningRig, rig_id)
    db.session.delete(rig)
    db.session.commit()
    return jsonify({"message": f"Mining rig {rig_id} deleted."})


# ──────────────────────────────────────────────────────────────────────────────
# Cooling Zones API
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/cooling/zones", methods=["GET"])
def get_cooling_zones():
    """Return all cooling zones."""
    zones = CoolingZone.query.order_by(CoolingZone.name).all()
    return jsonify([z.to_dict() for z in zones])


@app.route("/api/cooling/zones/<int:zone_id>", methods=["GET"])
def get_cooling_zone(zone_id):
    """Return a single cooling zone."""
    return jsonify(db.get_or_404(CoolingZone, zone_id).to_dict())


@app.route("/api/cooling/zones", methods=["POST"])
def create_cooling_zone():
    """Create a new cooling zone."""
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")
    name = payload.get("name", "").strip()
    if not name:
        abort(400, description="'name' is required.")

    zone = CoolingZone(
        name=name,
        zone_type=payload.get("zone_type", "CRAC"),
        capacity_kw=float(payload.get("capacity_kw", 0)),
        setpoint_temp_c=float(payload.get("setpoint_temp_c", 22)),
        max_temp_c=float(payload.get("max_temp_c", 30)),
        min_temp_c=float(payload.get("min_temp_c", 18)),
        is_active=bool(payload.get("is_active", True)),
        current_power_kw=float(payload.get("current_power_kw", 0)),
        current_temp_c=float(payload.get("current_temp_c", 22)),
        fan_speed_pct=float(payload.get("fan_speed_pct", 50)),
        coolant_flow_lpm=float(payload.get("coolant_flow_lpm", 0)),
    )
    db.session.add(zone)
    db.session.commit()
    return jsonify(zone.to_dict()), 201


@app.route("/api/cooling/zones/<int:zone_id>", methods=["PUT"])
def update_cooling_zone(zone_id):
    """Update cooling zone telemetry or setpoints."""
    zone = db.get_or_404(CoolingZone, zone_id)
    payload = request.get_json(silent=True)
    if not payload:
        abort(400, description="Request body must be JSON.")

    if "name" in payload:
        zone.name = payload["name"]
    if "zone_type" in payload:
        zone.zone_type = payload["zone_type"]
    if "is_active" in payload:
        zone.is_active = bool(payload["is_active"])
    for field in ("capacity_kw", "setpoint_temp_c", "max_temp_c", "min_temp_c",
                  "current_power_kw", "current_temp_c", "fan_speed_pct", "coolant_flow_lpm"):
        if field in payload:
            try:
                zone.__setattr__(field, float(payload[field]))
            except (TypeError, ValueError):
                abort(400, description=f"'{field}' must be a number.")

    zone.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(zone.to_dict())


@app.route("/api/cooling/zones/<int:zone_id>", methods=["DELETE"])
def delete_cooling_zone(zone_id):
    """Remove a cooling zone."""
    zone = db.get_or_404(CoolingZone, zone_id)
    db.session.delete(zone)
    db.session.commit()
    return jsonify({"message": f"Cooling zone {zone_id} deleted."})


# ──────────────────────────────────────────────────────────────────────────────
# AI Controller API
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/ai/analyze", methods=["POST"])
def ai_analyze():
    """
    Run AI analysis across all active systems and return recommended actions.
    Recommendations are saved to the database as un-executed AIAction records.
    """
    summary, recommendations = _ai_controller.analyze()
    return jsonify({"summary": summary, "recommendations": recommendations})


@app.route("/api/ai/execute", methods=["POST"])
def ai_execute():
    """
    Execute a list of previously recommended AIAction IDs.
    Body: { "action_ids": [1, 2, 3] }
    """
    payload = request.get_json(silent=True)
    if not payload or "action_ids" not in payload:
        abort(400, description="'action_ids' list is required.")
    action_ids = payload["action_ids"]
    if not isinstance(action_ids, list):
        abort(400, description="'action_ids' must be a list.")

    executed = _ai_controller.execute_actions(action_ids)
    return jsonify({"executed_action_ids": executed, "count": len(executed)})


@app.route("/api/ai/actions", methods=["GET"])
def get_ai_actions():
    """Return recent AI action log (newest first, max 200 records)."""
    actions = (
        AIAction.query
        .order_by(desc(AIAction.timestamp))
        .limit(200)
        .all()
    )
    return jsonify([a.to_dict() for a in actions])


# ──────────────────────────────────────────────────────────────────────────────
# Energy System Status API
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/api/energy/status", methods=["GET"])
def get_energy_status():
    """Return a consolidated real-time status of the entire energy system."""
    solar_farms   = SolarFarm.query.all()
    bess_units    = BessUnit.query.all()
    mining_rigs   = MiningRig.query.all()
    cooling_zones = CoolingZone.query.all()

    total_solar_capacity_kw = sum(f.capacity_kw for f in solar_farms)
    total_solar_output_kw   = sum(f.current_output_kw for f in solar_farms if f.is_active)
    total_bess_capacity_kwh = sum(b.capacity_kwh for b in bess_units)
    total_bess_stored_kwh   = sum(b.capacity_kwh * b.state_of_charge_pct / 100 for b in bess_units)
    avg_bess_soc            = (
        total_bess_stored_kwh / total_bess_capacity_kwh * 100
        if total_bess_capacity_kwh > 0 else 0.0
    )
    total_hash_rate_ths     = sum(r.current_hash_rate_ths for r in mining_rigs if r.is_active)
    total_mining_power_kw   = sum(r.current_power_w / 1000 for r in mining_rigs if r.is_active)
    total_cooling_power_kw  = sum(z.current_power_kw for z in cooling_zones if z.is_active)
    net_power_kw            = total_solar_output_kw - total_mining_power_kw - total_cooling_power_kw

    # Alerts
    alerts = []
    for rig in mining_rigs:
        if rig.chip_temp_c >= EnergyAIController.CHIP_TEMP_EMERGENCY:
            alerts.append({"severity": "critical", "message": f"Rig '{rig.name}': emergency temperature {rig.chip_temp_c}°C"})
        elif rig.chip_temp_c >= EnergyAIController.CHIP_TEMP_CRITICAL:
            alerts.append({"severity": "warning", "message": f"Rig '{rig.name}': critical temperature {rig.chip_temp_c}°C"})
    for bess in bess_units:
        if bess.temperature_c >= EnergyAIController.BESS_TEMP_MAX:
            alerts.append({"severity": "warning", "message": f"BESS '{bess.name}': temperature {bess.temperature_c}°C"})
        if bess.state_of_charge_pct <= EnergyAIController.BESS_SOC_MIN:
            alerts.append({"severity": "warning", "message": f"BESS '{bess.name}': critically low SOC {bess.state_of_charge_pct:.1f}%"})
    for zone in cooling_zones:
        if zone.current_temp_c > zone.max_temp_c:
            alerts.append({"severity": "critical", "message": f"Cooling zone '{zone.name}': temperature {zone.current_temp_c}°C exceeds max"})

    return jsonify({
        "solar": {
            "farm_count":        len(solar_farms),
            "active_count":      sum(1 for f in solar_farms if f.is_active),
            "capacity_kw":       total_solar_capacity_kw,
            "current_output_kw": round(total_solar_output_kw, 2),
        },
        "bess": {
            "unit_count":        len(bess_units),
            "capacity_kwh":      total_bess_capacity_kwh,
            "stored_kwh":        round(total_bess_stored_kwh, 2),
            "avg_soc_pct":       round(avg_bess_soc, 1),
        },
        "mining": {
            "rig_count":         len(mining_rigs),
            "active_count":      sum(1 for r in mining_rigs if r.is_active),
            "total_hash_rate_ths": round(total_hash_rate_ths, 2),
            "total_power_kw":    round(total_mining_power_kw, 2),
        },
        "cooling": {
            "zone_count":        len(cooling_zones),
            "active_count":      sum(1 for z in cooling_zones if z.is_active),
            "total_power_kw":    round(total_cooling_power_kw, 2),
        },
        "net_power_kw": round(net_power_kw, 2),
        "alerts":        alerts,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
