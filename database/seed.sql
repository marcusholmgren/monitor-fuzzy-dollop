-- seed.sql

-- 1. Seed Houses
INSERT INTO houses (id, name, address) VALUES
    ('0192a000-0001-7000-8000-000000000001', 'Villa Stockholm', 'Drottninggatan 12, Stockholm'),
    ('0192a000-0002-7000-8000-000000000002', 'Gothenburg Cabin', 'Kungsportsavenyen 5, Gothenburg'),
    ('0192a000-0003-7000-8000-000000000003', 'Malmo Apartment', 'Stortorget 8, Malmo')
ON CONFLICT (id) DO NOTHING;

-- 2. Seed Sensors (Grouped by House)
INSERT INTO sensors (id, house_id, name, sensor_type) VALUES
    -- Villa Stockholm (3 sensors)
    ('0192a100-0001-7000-8000-000000000001', '0192a000-0001-7000-8000-000000000001', 'Living Room Temp', 'temperature'),
    ('0192a100-0002-7000-8000-000000000002', '0192a000-0001-7000-8000-000000000001', 'Basement Humidity', 'humidity'),
    ('0192a100-0003-7000-8000-000000000003', '0192a000-0001-7000-8000-000000000001', 'Attic Temp', 'temperature'),

    -- Gothenburg Cabin (2 sensors)
    ('0192a100-0004-7000-8000-000000000004', '0192a000-0002-7000-8000-000000000002', 'Sauna Thermometer', 'temperature'),
    ('0192a100-0005-7000-8000-000000000005', '0192a000-0002-7000-8000-000000000002', 'Living Room Air Quality', 'co2'),

    -- Malmo Apartment (2 sensors)
    ('0192a100-0006-7000-8000-000000000006', '0192a000-0003-7000-8000-000000000003', 'Kitchen Humidity', 'humidity'),
    ('0192a100-0007-7000-8000-000000000007', '0192a000-0003-7000-8000-000000000003', 'Balcony Weather', 'temperature')
ON CONFLICT (id) DO NOTHING;

-- 3. Seed Out-of-Order Historical Readings (Spanning 2018 to 2026)
INSERT INTO readings (house_id, sensor_id, recorded_at, metric_value, metadata) VALUES
    -- 2018 Backfill Event
    ('0192a000-0001-7000-8000-000000000001', '0192a100-0001-7000-8000-000000000001', '2018-05-14 12:00:00+00', 19.5, '{"firmware": "v1.0"}'::jsonb),

    -- 2021 Events
    ('0192a000-0001-7000-8000-000000000001', '0192a100-0002-7000-8000-000000000002', '2021-11-03 08:30:00+00', 65.2, '{"unit": "%"}'::jsonb),
    ('0192a000-0002-7000-8000-000000000002', '0192a100-0004-7000-8000-000000000004', '2021-12-25 18:00:00+00', 78.4, '{"sauna_status": "heating"}'::jsonb),

    -- 2024 Events
    ('0192a000-0001-7000-8000-000000000001', '0192a100-0001-7000-8000-000000000001', '2024-06-20 14:10:00+00', 23.8, '{"firmware": "v2.1"}'::jsonb),
    ('0192a000-0003-7000-8000-000000000003', '0192a100-0006-7000-8000-000000000006', '2024-09-12 11:45:00+00', 48.0, '{}'::jsonb),

    -- 2026 Recent Events
    ('0192a000-0002-7000-8000-000000000002', '0192a100-0005-7000-8000-000000000005', '2026-10-01 09:00:00+00', 420.0, '{"calibrated": true}'::jsonb),
    ('0192a000-0001-7000-8000-000000000001', '0192a100-0001-7000-8000-000000000001', '2026-10-08 14:00:00+00', 21.2, '{"source": "live_stream"}'::jsonb),
    ('0192a000-0001-7000-8000-000000000001', '0192a100-0001-7000-8000-000000000001', '2026-10-08 15:30:00+00', 21.0, '{"source": "live_stream"}'::jsonb)
ON CONFLICT (sensor_id, recorded_at) DO NOTHING;
