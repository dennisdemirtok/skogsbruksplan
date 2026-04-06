import axios, { AxiosError } from 'axios';
import type {
  AuthResponse,
  LoginPayload,
  RegisterPayload,
  User,
  Property,
  Stand,
  StandCollection,
  ForestPlan,
  ForestData,
  FieldData,
  EconomicData,
  ActionProposal,
} from '@/types';

/* ───────── snake_case ↔ camelCase converters ───────── */

function snakeToCamelStr(str: string): string {
  return str.replace(/_([a-z0-9])/g, (_, char: string) => char.toUpperCase());
}

function camelToSnakeStr(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

/** Convert all object keys from snake_case to camelCase (for responses) */
function snakeToCamelKeys(obj: unknown): unknown {
  if (obj === null || obj === undefined || typeof obj !== 'object') return obj;
  if (obj instanceof Blob || obj instanceof ArrayBuffer || obj instanceof FormData) return obj;
  if (Array.isArray(obj)) return obj.map(snakeToCamelKeys);
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    result[snakeToCamelStr(key)] = snakeToCamelKeys(value);
  }
  return result;
}

/** Convert all object keys from camelCase to snake_case (for requests) */
function camelToSnakeKeys(obj: unknown): unknown {
  if (obj === null || obj === undefined || typeof obj !== 'object') return obj;
  if (obj instanceof Blob || obj instanceof ArrayBuffer || obj instanceof FormData) return obj;
  if (Array.isArray(obj)) return obj.map(camelToSnakeKeys);
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    // Don't transform GeoJSON keys (type, coordinates, features, properties, geometry, etc.)
    const geoJsonKeys = new Set([
      'type', 'coordinates', 'features', 'properties', 'geometry',
      'geometries', 'bbox', 'crs', 'Feature', 'FeatureCollection',
      'Point', 'MultiPoint', 'LineString', 'MultiLineString',
      'Polygon', 'MultiPolygon', 'GeometryCollection',
    ]);
    const newKey = geoJsonKeys.has(key) ? key : camelToSnakeStr(key);
    result[newKey] = camelToSnakeKeys(value);
  }
  return result;
}

/* ───────── Axios instance ───────── */

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor: attach JWT + convert camelCase → snake_case
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('skogsplan_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Convert request body keys from camelCase to snake_case
  if (config.data && typeof config.data === 'object' && !(config.data instanceof FormData)) {
    config.data = camelToSnakeKeys(config.data);
  }
  // Convert query params keys from camelCase to snake_case
  if (config.params && typeof config.params === 'object') {
    config.params = camelToSnakeKeys(config.params);
  }
  return config;
});

// Response interceptor: convert snake_case → camelCase + handle 401
api.interceptors.response.use(
  (res) => {
    if (res.data && typeof res.data === 'object' && !(res.data instanceof Blob)) {
      res.data = snakeToCamelKeys(res.data);
    }
    return res;
  },
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('skogsplan_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    const message = error.response?.data?.detail || error.message || 'Ett oväntat fel uppstod';
    return Promise.reject(new Error(message));
  },
);

/* ───────── Auth ───────── */

export const authApi = {
  login: async (payload: LoginPayload): Promise<AuthResponse> => {
    const { data } = await api.post<AuthResponse>('/auth/login', payload);
    return data;
  },

  register: async (payload: RegisterPayload): Promise<AuthResponse> => {
    const { data } = await api.post<AuthResponse>('/auth/register', payload);
    return data;
  },

  getMe: async (): Promise<User> => {
    const { data } = await api.get<User>('/auth/me');
    return data;
  },
};

/* ───────── Properties ───────── */

export const propertiesApi = {
  list: async (): Promise<Property[]> => {
    const { data } = await api.get<Property[]>('/properties');
    if (Array.isArray(data)) return data;
    // Fallback for GeoJSON FeatureCollection format
    const fc = data as unknown as { type?: string; features?: Array<{ id: string; properties: Record<string, unknown>; geometry?: unknown }> };
    if (fc?.type === 'FeatureCollection' && Array.isArray(fc.features)) {
      return fc.features.map((f) => ({
        id: String(f.id),
        name: String(f.properties?.designation || f.properties?.name || ''),
        municipality: String(f.properties?.municipality || ''),
        county: String(f.properties?.county || ''),
        propertyDesignation: String(f.properties?.designation || f.properties?.propertyDesignation || ''),
        totalArea: Number(f.properties?.totalAreaHa || f.properties?.totalArea || 0),
        productiveArea: Number(f.properties?.productiveForestHa || f.properties?.productiveArea || 0),
        boundaryGeojson: f.geometry ? { type: 'FeatureCollection' as const, features: [{ type: 'Feature' as const, geometry: f.geometry as GeoJSON.Geometry, properties: {} }] } : null,
        ownerId: String(f.properties?.ownerId || ''),
        createdAt: String(f.properties?.createdAt || ''),
        updatedAt: String(f.properties?.updatedAt || ''),
      })) as Property[];
    }
    return [];
  },

  get: async (id: string): Promise<Property> => {
    const { data } = await api.get<Property>(`/properties/${id}`);
    return data;
  },

  create: async (payload: Partial<Property>): Promise<Property> => {
    const { data } = await api.post<Property>('/properties', payload);
    return data;
  },

  update: async (id: string, payload: Partial<Property>): Promise<Property> => {
    const { data } = await api.put<Property>(`/properties/${id}`, payload);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/properties/${id}`);
  },
};

/* ───────── Stands ───────── */
// Backend routes: /stands/property/{property_id}, /stands/{stand_id}, /stands (POST)

export const standsApi = {
  listByProperty: async (propertyId: string): Promise<StandCollection> => {
    const { data } = await api.get<StandCollection>(`/stands/property/${propertyId}`);
    return data;
  },

  get: async (_propertyId: string, standId: string): Promise<Stand> => {
    const { data } = await api.get<Stand>(`/stands/${standId}`);
    return data;
  },

  create: async (propertyId: string, payload: Partial<Stand> & { geometry?: GeoJSON.Geometry }): Promise<Stand> => {
    const { geometry, ...rest } = payload;
    const body = { ...rest, propertyId, standNumber: payload.standNumber || 1, geometryGeojson: geometry || undefined };
    const { data } = await api.post<Stand>('/stands', body);
    return data;
  },

  update: async (_propertyId: string, standId: string, payload: Partial<Stand>): Promise<Stand> => {
    const { data } = await api.put<Stand>(`/stands/${standId}`, payload);
    return data;
  },

  delete: async (_propertyId: string, standId: string): Promise<void> => {
    await api.delete(`/stands/${standId}`);
  },

  bulkUpdate: async (_propertyId: string, standIds: string[], updates: Partial<Stand>): Promise<Stand[]> => {
    const { data } = await api.put<Stand[]>('/stands/bulk/update', { standIds, ...updates });
    return data;
  },
};

/* ───────── Plans ───────── */

export const plansApi = {
  list: async (propertyId?: string): Promise<ForestPlan[]> => {
    const params = propertyId ? { propertyId } : {};
    const { data } = await api.get<ForestPlan[]>('/plans', { params });
    return Array.isArray(data) ? data : [];
  },

  get: async (id: string): Promise<ForestPlan> => {
    const { data } = await api.get<ForestPlan>(`/plans/${id}`);
    return data;
  },

  create: async (payload: Partial<ForestPlan>): Promise<ForestPlan> => {
    const { data } = await api.post<ForestPlan>('/plans', payload);
    return data;
  },

  update: async (id: string, payload: Partial<ForestPlan>): Promise<ForestPlan> => {
    const { data } = await api.put<ForestPlan>(`/plans/${id}`, payload);
    return data;
  },

  publish: async (id: string): Promise<ForestPlan> => {
    const { data } = await api.post<ForestPlan>(`/plans/${id}/publish`);
    return data;
  },

  getPdf: async (id: string): Promise<Blob> => {
    const { data } = await api.get(`/plans/${id}/pdf`, { responseType: 'blob' });
    return data as Blob;
  },

  getShared: async (token: string): Promise<ForestPlan> => {
    const { data } = await api.get<ForestPlan>(`/plans/shared/${token}`);
    return data;
  },
};

/* ───────── Geodata ───────── */
// Backend routes: /geodata/forest-data?bbox=..., /geodata/bark-beetle-risk?bbox=...

export const geodataApi = {
  getForestData: async (bbox: string): Promise<ForestData> => {
    const { data } = await api.get<ForestData>('/geodata/forest-data', { params: { bbox } });
    return data;
  },

  lookupProperty: async (designation: string): Promise<{
    designation: string;
    municipality?: string;
    county?: string;
    geometry?: unknown;
    areaHa?: number;
    lantmaterietId?: string;
    lastUpdated?: string;
    source?: string;
  }> => {
    const { data } = await api.get('/geodata/property-lookup', { params: { designation } });
    return data as {
      designation: string;
      municipality?: string;
      county?: string;
      geometry?: unknown;
      areaHa?: number;
      lantmaterietId?: string;
      lastUpdated?: string;
      source?: string;
    };
  },

  /** Search for properties by municipality and/or tract name */
  searchProperties: async (params: {
    municipality?: string;
    trakt?: string;
    limit?: number;
  }): Promise<{
    query: string;
    resultsCount: number;
    results: Array<{
      designation: string;
      municipality: string;
      kommunCode: string;
      trakt: string;
      block: string;
      enhet: number;
      lastUpdated: string;
    }>;
  }> => {
    const { data } = await api.get('/geodata/property-search', { params });
    return data as {
      query: string;
      resultsCount: number;
      results: Array<{
        designation: string;
        municipality: string;
        kommunCode: string;
        trakt: string;
        block: string;
        enhet: number;
        lastUpdated: string;
      }>;
    };
  },

  getBarkBeetleRisk: async (bbox: string): Promise<{ bbox: number[]; riskData: Record<string, unknown> }> => {
    const { data } = await api.get('/geodata/bark-beetle-risk', { params: { bbox } });
    return data as { bbox: number[]; riskData: Record<string, unknown> };
  },
};

/* ───────── Field Data ───────── */
// Backend routes: /fielddata/stand/{stand_id}, /fielddata/photo

export const fieldDataApi = {
  listByStand: async (standId: string): Promise<FieldData[]> => {
    const { data } = await api.get<FieldData[]>(`/fielddata/stand/${standId}`);
    return data;
  },

  create: async (standId: string, payload: Partial<FieldData>): Promise<FieldData> => {
    const { data } = await api.post<FieldData>(`/fielddata/stand/${standId}`, payload);
    return data;
  },

  uploadPhoto: async (file: File): Promise<{ url: string }> => {
    const form = new FormData();
    form.append('file', file);
    const { data } = await api.post<{ url: string }>('/fielddata/photo', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
};

/* ───────── Economics & Analytics ───────── */
// Backend routes: /properties/{id}/economics, /properties/{id}/actions, /properties/{id}/summary

export const economicsApi = {
  getPropertyEconomics: async (propertyId: string): Promise<EconomicData> => {
    const { data } = await api.get<EconomicData>(`/properties/${propertyId}/economics`);
    return data;
  },

  getActionProposals: async (propertyId: string): Promise<ActionProposal[]> => {
    const { data } = await api.get<ActionProposal[]>(`/properties/${propertyId}/actions`);
    return data;
  },

  getPropertySummary: async (propertyId: string): Promise<Record<string, unknown>> => {
    const { data } = await api.get(`/properties/${propertyId}/summary`);
    return data as Record<string, unknown>;
  },
};

/* ───────── Weather & Alerts ───────── */

export const weatherApi = {
  getForecast: async (propertyId: string): Promise<Record<string, unknown>> => {
    const { data } = await api.get(`/weather/forecast/${propertyId}`);
    return data as Record<string, unknown>;
  },

  getWarnings: async (): Promise<Record<string, unknown>> => {
    const { data } = await api.get('/weather/warnings');
    return data as Record<string, unknown>;
  },

  getAlerts: async (propertyId: string): Promise<Record<string, unknown>> => {
    const { data } = await api.get(`/weather/alerts/${propertyId}`);
    return data as Record<string, unknown>;
  },
};

/* ─── Satellite / Sentinel-2 ──────────────────────────────── */

export const satelliteApi = {
  /** Search available Sentinel-2 scenes for a property */
  searchScenes: async (propertyId: string, daysBack = 60): Promise<Record<string, unknown>> => {
    const { data } = await api.get(`/satellite/scenes/${propertyId}`, {
      params: { days_back: daysBack },
    });
    return data as Record<string, unknown>;
  },

  /** Get latest NDVI per stand (lightweight, for dashboard widget) */
  getNdvi: async (propertyId: string): Promise<Record<string, unknown>> => {
    const { data } = await api.get(`/satellite/ndvi/${propertyId}`);
    return data as Record<string, unknown>;
  },

  /** Full health analysis with change detection (heavier, for detail view) */
  getHealthAnalysis: async (propertyId: string, referenceMonths = 6): Promise<Record<string, unknown>> => {
    const { data } = await api.get(`/satellite/health/${propertyId}`, {
      params: { reference_months: referenceMonths },
    });
    return data as Record<string, unknown>;
  },
};

export default api;
