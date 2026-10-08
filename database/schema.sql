-- schema.sql

-- Clean existing tables for local resets
DROP TABLE IF EXISTS readings;
DROP TABLE IF EXISTS sensors;
DROP TABLE IF EXISTS houses;

-- 1. Houses Table
CREATE TABLE houses (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    name VARCHAR(100) NOT NULL,
    address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 2. Sensors Table
CREATE TABLE sensors (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    house_id UUID NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    sensor_type VARCHAR(50) NOT NULL, -- e.g., 'temperature', 'humidity', 'co2'
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    -- Enforces composite uniqueness so foreign keys can validate the house-sensor pair
    CONSTRAINT uq_sensor_house UNIQUE (id, house_id)
);

-- 3. Sensor Readings Table
CREATE TABLE readings (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    house_id UUID NOT NULL,
    sensor_id UUID NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    -- Composite FK: Guarantees sensor exists AND belongs to the stated house
    CONSTRAINT fk_readings_sensor_house
        FOREIGN KEY (sensor_id, house_id)
        REFERENCES sensors(id, house_id)
        ON DELETE RESTRICT,

    -- Deduplication constraint for ON CONFLICT DO NOTHING
    CONSTRAINT uq_sensor_reading_time UNIQUE (sensor_id, recorded_at)
);

-- 4. Keyset Pagination Indexes (DESC chronological scan)
CREATE INDEX idx_readings_sensor_keyset
    ON readings (sensor_id, recorded_at DESC, id DESC);

CREATE INDEX idx_readings_house_keyset
    ON readings (house_id, recorded_at DESC, id DESC);

CREATE INDEX idx_readings_global_keyset
    ON readings (recorded_at DESC, id DESC);
