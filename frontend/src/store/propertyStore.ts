import { create } from 'zustand';
import type { Property, StandCollection, Stand } from '@/types';
import { propertiesApi, standsApi } from '@/services/api';

interface PropertyState {
  /* Data */
  properties: Property[];
  currentProperty: Property | null;
  stands: StandCollection;

  /* Loading states */
  propertiesLoading: boolean;
  propertyLoading: boolean;
  standsLoading: boolean;
  saving: boolean;
  error: string | null;

  /* Actions – Properties */
  fetchProperties: () => Promise<void>;
  fetchProperty: (id: string) => Promise<void>;
  createProperty: (payload: Partial<Property>) => Promise<Property>;
  updateProperty: (id: string, payload: Partial<Property>) => Promise<void>;
  deleteProperty: (id: string) => Promise<void>;
  setCurrentProperty: (property: Property | null) => void;

  /* Actions – Stands */
  fetchStands: (propertyId: string) => Promise<void>;
  createStand: (propertyId: string, payload: Partial<Stand> & { geometry: GeoJSON.Geometry }) => Promise<Stand>;
  updateStand: (propertyId: string, standId: string, payload: Partial<Stand>) => Promise<void>;
  deleteStand: (propertyId: string, standId: string) => Promise<void>;
  bulkUpdateStands: (propertyId: string, stands: Partial<Stand>[]) => Promise<void>;
  setStands: (stands: StandCollection) => void;

  clearError: () => void;
}

const emptyCollection: StandCollection = {
  type: 'FeatureCollection',
  features: [],
};

export const usePropertyStore = create<PropertyState>((set, get) => ({
  properties: [],
  currentProperty: null,
  stands: emptyCollection,
  propertiesLoading: false,
  propertyLoading: false,
  standsLoading: false,
  saving: false,
  error: null,

  /* ── Properties ── */

  fetchProperties: async () => {
    set({ propertiesLoading: true, error: null });
    try {
      const properties = await propertiesApi.list();
      set({ properties, propertiesLoading: false });
    } catch (err) {
      set({
        propertiesLoading: false,
        error: err instanceof Error ? err.message : 'Kunde inte hämta fastigheter',
      });
    }
  },

  fetchProperty: async (id) => {
    set({ propertyLoading: true, error: null });
    try {
      const property = await propertiesApi.get(id);
      set({ currentProperty: property, propertyLoading: false });
    } catch (err) {
      set({
        propertyLoading: false,
        error: err instanceof Error ? err.message : 'Kunde inte hämta fastighet',
      });
    }
  },

  createProperty: async (payload) => {
    set({ saving: true, error: null });
    try {
      const property = await propertiesApi.create(payload);
      set((state) => ({
        properties: [...state.properties, property],
        saving: false,
      }));
      return property;
    } catch (err) {
      set({
        saving: false,
        error: err instanceof Error ? err.message : 'Kunde inte skapa fastighet',
      });
      throw err;
    }
  },

  updateProperty: async (id, payload) => {
    set({ saving: true, error: null });
    try {
      const updated = await propertiesApi.update(id, payload);
      set((state) => ({
        properties: state.properties.map((p) => (p.id === id ? updated : p)),
        currentProperty: state.currentProperty?.id === id ? updated : state.currentProperty,
        saving: false,
      }));
    } catch (err) {
      set({
        saving: false,
        error: err instanceof Error ? err.message : 'Kunde inte uppdatera fastighet',
      });
      throw err;
    }
  },

  deleteProperty: async (id) => {
    set({ saving: true, error: null });
    try {
      await propertiesApi.delete(id);
      set((state) => ({
        properties: state.properties.filter((p) => p.id !== id),
        currentProperty: state.currentProperty?.id === id ? null : state.currentProperty,
        saving: false,
      }));
    } catch (err) {
      set({
        saving: false,
        error: err instanceof Error ? err.message : 'Kunde inte radera fastighet',
      });
      throw err;
    }
  },

  setCurrentProperty: (property) => set({ currentProperty: property }),

  /* ── Stands ── */

  fetchStands: async (propertyId) => {
    set({ standsLoading: true, error: null });
    try {
      const stands = await standsApi.listByProperty(propertyId);
      set({ stands, standsLoading: false });
    } catch (err) {
      set({
        standsLoading: false,
        error: err instanceof Error ? err.message : 'Kunde inte hämta avdelningar',
      });
    }
  },

  createStand: async (propertyId, payload) => {
    set({ saving: true, error: null });
    try {
      const stand = await standsApi.create(propertyId, payload);
      // Refetch stands to get GeoJSON with new feature
      await get().fetchStands(propertyId);
      set({ saving: false });
      return stand;
    } catch (err) {
      set({
        saving: false,
        error: err instanceof Error ? err.message : 'Kunde inte skapa avdelning',
      });
      throw err;
    }
  },

  updateStand: async (propertyId, standId, payload) => {
    set({ saving: true, error: null });
    try {
      await standsApi.update(propertyId, standId, payload);
      await get().fetchStands(propertyId);
      set({ saving: false });
    } catch (err) {
      set({
        saving: false,
        error: err instanceof Error ? err.message : 'Kunde inte uppdatera avdelning',
      });
      throw err;
    }
  },

  deleteStand: async (propertyId, standId) => {
    set({ saving: true, error: null });
    try {
      await standsApi.delete(propertyId, standId);
      set((state) => ({
        stands: {
          ...state.stands,
          features: state.stands.features.filter((f) => f.properties.id !== standId),
        },
        saving: false,
      }));
    } catch (err) {
      set({
        saving: false,
        error: err instanceof Error ? err.message : 'Kunde inte radera avdelning',
      });
      throw err;
    }
  },

  bulkUpdateStands: async (propertyId, stands) => {
    set({ saving: true, error: null });
    try {
      const standIds = stands.filter((s) => s.id).map((s) => s.id as string);
      const updates = stands.length > 0 ? stands[0] : {};
      await standsApi.bulkUpdate(propertyId, standIds, updates);
      await get().fetchStands(propertyId);
      set({ saving: false });
    } catch (err) {
      set({
        saving: false,
        error: err instanceof Error ? err.message : 'Kunde inte uppdatera avdelningar',
      });
      throw err;
    }
  },

  setStands: (stands) => set({ stands }),
  clearError: () => set({ error: null }),
}));
