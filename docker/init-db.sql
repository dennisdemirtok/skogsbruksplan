-- SkogsplanSaaS Database Initialization
-- PostGIS + UUID + trigram extensions

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email VARCHAR(255) UNIQUE NOT NULL,
  hashed_password VARCHAR(255) NOT NULL,
  full_name VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'owner' CHECK (role IN ('consultant', 'owner', 'reader', 'admin')),
  organization_id UUID,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- PROPERTIES (Fastigheter)
-- ============================================================

CREATE TABLE properties (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  designation VARCHAR(255) NOT NULL,
  municipality VARCHAR(255),
  county VARCHAR(255),
  geometry GEOMETRY(MultiPolygon, 3006),
  total_area_ha FLOAT,
  productive_forest_ha FLOAT,
  owner_id UUID REFERENCES users(id),
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- STANDS (Avdelningar / Bestand)
-- ============================================================

CREATE TABLE stands (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
  stand_number INTEGER NOT NULL,
  geometry GEOMETRY(Polygon, 3006),
  area_ha FLOAT,
  -- Forest data
  volume_m3_per_ha FLOAT,
  total_volume_m3 FLOAT,
  mean_height_m FLOAT,
  basal_area_m2 FLOAT,
  mean_diameter_cm FLOAT,
  age_years INTEGER,
  site_index FLOAT,
  -- Species percentages
  pine_pct FLOAT DEFAULT 0,
  spruce_pct FLOAT DEFAULT 0,
  deciduous_pct FLOAT DEFAULT 0,
  contorta_pct FLOAT DEFAULT 0,
  -- Management
  target_class VARCHAR(5) CHECK (target_class IN ('PG', 'NS', 'NO', 'PF')),
  proposed_action VARCHAR(20) CHECK (proposed_action IN ('slutavverkning', 'gallring', 'rojning', 'foryngring', 'ingen')),
  action_urgency INTEGER CHECK (action_urgency BETWEEN 1 AND 5),
  action_year INTEGER,
  -- Economics
  timber_volume_m3 FLOAT,
  pulpwood_volume_m3 FLOAT,
  gross_value_sek FLOAT,
  harvesting_cost_sek FLOAT,
  net_value_sek FLOAT,
  -- Risk
  bark_beetle_risk FLOAT,
  -- Meta
  data_source VARCHAR(10) DEFAULT 'manual' CHECK (data_source IN ('auto', 'field', 'manual')),
  field_verified BOOLEAN DEFAULT FALSE,
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(property_id, stand_number)
);

-- ============================================================
-- FIELD DATA (Faltdata)
-- ============================================================

CREATE TABLE field_data (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  stand_id UUID REFERENCES stands(id) ON DELETE CASCADE,
  recorded_by UUID REFERENCES users(id),
  recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  gps_lat FLOAT,
  gps_lon FLOAT,
  relascope_value FLOAT,
  sample_trees JSONB DEFAULT '[]',
  soil_moisture VARCHAR(20) CHECK (soil_moisture IN ('torr', 'frisk', 'fuktig', 'blot')),
  nature_values JSONB DEFAULT '{}',
  photos JSONB DEFAULT '[]',
  notes TEXT
);

-- ============================================================
-- FOREST PLANS (Skogsbruksplaner)
-- ============================================================

CREATE TABLE forest_plans (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  version INTEGER DEFAULT 1,
  status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  created_by UUID REFERENCES users(id),
  share_token VARCHAR(255) UNIQUE,
  pdf_url TEXT,
  valid_from DATE,
  valid_to DATE,
  certification VARCHAR(10) DEFAULT 'none' CHECK (certification IN ('none', 'PEFC', 'FSC', 'both')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_properties_owner ON properties(owner_id);
CREATE INDEX idx_properties_geometry ON properties USING GIST(geometry);
CREATE INDEX idx_stands_property ON stands(property_id);
CREATE INDEX idx_stands_geometry ON stands USING GIST(geometry);
CREATE INDEX idx_stands_target_class ON stands(target_class);
CREATE INDEX idx_field_data_stand ON field_data(stand_id);
CREATE INDEX idx_plans_property ON forest_plans(property_id);
CREATE INDEX idx_plans_share_token ON forest_plans(share_token);

-- ============================================================
-- TRIGGER: auto-update updated_at columns
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_properties_updated_at
  BEFORE UPDATE ON properties
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_stands_updated_at
  BEFORE UPDATE ON stands
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_plans_updated_at
  BEFORE UPDATE ON forest_plans
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
