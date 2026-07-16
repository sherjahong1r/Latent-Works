-- Kimyo reaktori uchun SCADA loyihasi -- PostgreSQL sxemasi

CREATE TABLE IF NOT EXISTS sensor_readings (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMP NOT NULL DEFAULT NOW(),
    temperature     REAL,
    pressure        REAL,
    heat_output     REAL,
    speed           REAL,
    ph              REAL,
    flow_rate       REAL,
    level_pct       REAL,
    vibration       REAL,
    humidity        REAL,
    voltage         REAL,
    current_a       REAL
);

CREATE TABLE IF NOT EXISTS actuator_states (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMP NOT NULL DEFAULT NOW(),
    fan_on          BOOLEAN,
    relief_valve_open BOOLEAN,
    neutralizer_pump_on BOOLEAN,
    agitator_on     BOOLEAN,
    trip_emergency  BOOLEAN
);

CREATE TABLE IF NOT EXISTS alarms (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMP NOT NULL DEFAULT NOW(),
    severity        TEXT,           -- WARNING | TRIP
    message         TEXT,
    acknowledged    BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS ai_insights (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMP NOT NULL DEFAULT NOW(),
    sensor_name     TEXT,
    finding         TEXT,           -- masalan: "anomaliya aniqlandi"
    z_score         REAL
);

CREATE TABLE IF NOT EXISTS mes_batches (
    id              SERIAL PRIMARY KEY,
    batch_no        TEXT,
    started_at      TIMESTAMP,
    ended_at        TIMESTAMP,
    good_units      INTEGER DEFAULT 0,
    downtime_sec    INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'RUNNING'   -- RUNNING | COMPLETED | STOPPED
);

CREATE TABLE IF NOT EXISTS erp_costs (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMP NOT NULL DEFAULT NOW(),
    batch_no        TEXT,
    raw_material_cost REAL,
    energy_cost     REAL,
    estimated_output_value REAL
);


