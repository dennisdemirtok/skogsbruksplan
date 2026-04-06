import type { Feature, FeatureCollection, Polygon, MultiPolygon } from 'geojson';

/* ───────── User & Auth ───────── */

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'consultant' | 'owner' | 'viewer';
  organization?: string;
  createdAt: string;
}

export interface AuthResponse {
  accessToken: string;
  tokenType: string;
  user: User;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
  role: 'consultant' | 'owner';
  organization?: string;
}

/* ───────── Property ───────── */

export interface Property {
  id: string;
  name: string;
  municipality: string;
  county: string;
  propertyDesignation: string; // fastighetsbeteckning
  totalArea: number; // ha
  productiveArea: number; // ha
  boundaryGeojson: FeatureCollection<Polygon | MultiPolygon> | null;
  ownerId: string;
  ownerName?: string;
  createdAt: string;
  updatedAt: string;
}

/* ───────── Stand (Avdelning) ───────── */

export type TargetClass = 'PG' | 'PF' | 'NS' | 'NO' | 'K';

export type ActionType =
  | 'slutavverkning'
  | 'gallring'
  | 'rojning'
  | 'foryngring'
  | 'ingen'
  | 'naturvard'
  | 'ovrig';

export type SoilMoisture = 'torr' | 'frisk' | 'fuktig' | 'blot';

export interface Stand {
  id: string;
  propertyId: string;
  standNumber: number;
  areaHa: number | null; // ha
  targetClass: TargetClass | null;
  siteIndex: number | null; // bonitet SI
  ageYears: number | null; // year
  volumeM3PerHa: number | null; // m3sk/ha
  totalVolumeM3: number | null; // m3sk
  basalAreaM2: number | null; // grundyta m2/ha
  meanHeightM: number | null; // m
  meanDiameterCm: number | null; // cm
  pinePct: number | null;
  sprucePct: number | null;
  deciduousPct: number | null;
  contortaPct: number | null;

  /* Action proposal */
  proposedAction: ActionType | null;
  actionUrgency: number | null; // 1-5
  actionYear: number | null;

  /* Economy */
  timberVolumeM3: number | null;
  pulpwoodVolumeM3: number | null;
  grossValueSek: number | null; // SEK
  harvestingCostSek: number | null;
  netValueSek: number | null;

  /* Risk */
  barkBeetleRisk: number | null;

  /* Data source */
  dataSource: string | null;
  fieldVerified: boolean;
  notes: string | null;

  /* Geometry (only in single-stand response, not GeoJSON) */
  geometryGeojson?: Record<string, unknown> | null;

  createdAt: string;
  updatedAt: string;
}

export interface StandProperties extends Omit<Stand, 'id' | 'createdAt' | 'updatedAt' | 'geometryGeojson'> {
  id: string;
}

export type StandFeature = Feature<Polygon | MultiPolygon, StandProperties>;
export type StandCollection = FeatureCollection<Polygon | MultiPolygon, StandProperties>;

/* ───────── Forest Data (raster-derived) ───────── */

export interface ForestData {
  bbox: number[];
  data: Record<string, unknown>;
}

/* ───────── Field Data ───────── */

export interface SampleTree {
  species: 'tall' | 'gran' | 'bjork' | 'ovrig';
  diameter: number; // cm (dbh_cm)
  height: number; // m (height_m)
}

export interface FieldData {
  id: string;
  standId: string;
  recordedBy: string;
  recordedAt: string;
  gpsLat: number | null;
  gpsLon: number | null;
  relascopeValue: number | null;
  sampleTrees: SampleTree[] | null;
  soilMoisture: SoilMoisture | null;
  natureValues: Record<string, unknown> | null;
  photos: string[] | null;
  notes: string | null;
}

/* ───────── Forest Plan ───────── */

export interface ForestPlan {
  id: string;
  propertyId: string;
  name: string;
  version: number;
  status: 'draft' | 'published' | 'archived';
  createdBy: string;
  shareToken: string | null;
  pdfUrl: string | null;
  validFrom: string | null; // ISO date
  validTo: string | null; // ISO date
  certification: 'none' | 'PEFC' | 'FSC' | 'both';
  createdAt: string;
  updatedAt: string;
  // Extended fields from PlanDetailResponse
  propertyDesignation?: string;
  standCount?: number;
  totalAreaHa?: number;
}

/* ───────── Action Proposal ───────── */

export interface ActionProposal {
  standId: string;
  standNumber: number;
  areaHa: number;
  proposedAction: ActionType | null;
  actionUrgency: number | null;
  actionYear: number | null;
  reasoning: string;
  timberVolumeM3: number | null;
  pulpwoodVolumeM3: number | null;
  netValueSek: number | null;
}

/* ───────── Economic Data ───────── */

export interface EconomicData {
  propertyId: string;
  totalTimberVolumeM3: number;
  totalPulpwoodVolumeM3: number;
  totalGrossValueSek: number;
  totalHarvestingCostSek: number;
  totalNetValueSek: number;
  totalNpv10yr: number;
  standEconomics: Array<{
    standId: string;
    standNumber: number;
    areaHa: number;
    timberVolumeM3: number;
    pulpwoodVolumeM3: number;
    grossValueSek: number;
    harvestingCostSek: number;
    netValueSek: number;
  }>;
  actionsByYear: Array<{
    year: number;
    action: string;
    standCount: number;
    totalAreaHa: number;
    totalNetValueSek: number;
  }>;
}

/* ───────── API Response wrappers ───────── */

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  detail: string;
  status: number;
}
