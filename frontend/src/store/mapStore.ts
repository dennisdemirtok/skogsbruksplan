import { create } from 'zustand';

export type StandColorMode = 'targetClass' | 'action' | 'age' | 'volume';

interface LayerVisibility {
  ortofoto: boolean;
  stands: boolean;
  standLabels: boolean;
  barkBeetle: boolean;
  soilMoisture: boolean;
  propertyBoundary: boolean;
}

interface MapState {
  /* View */
  mapCenter: [number, number]; // [lng, lat]
  mapZoom: number;

  /* Selection */
  selectedStandId: string | null;
  hoveredStandId: string | null;
  editingStandId: string | null;

  /* Drawing */
  drawMode: boolean;
  drawType: 'polygon' | 'line' | 'select' | null;

  /* Layers */
  layers: LayerVisibility;
  standColorMode: StandColorMode;
  ortofotoOpacity: number;
  barkBeetleOpacity: number;
  soilMoistureOpacity: number;

  /* Context menu */
  contextMenu: { x: number; y: number; standId: string } | null;

  /* Undo/Redo */
  undoStack: string[]; // serialised geometry snapshots
  redoStack: string[];

  /* Actions */
  setMapCenter: (center: [number, number]) => void;
  setMapZoom: (zoom: number) => void;
  setSelectedStand: (id: string | null) => void;
  setHoveredStand: (id: string | null) => void;
  setEditingStand: (id: string | null) => void;
  setDrawMode: (active: boolean, type?: 'polygon' | 'line' | 'select') => void;
  toggleLayer: (layer: keyof LayerVisibility) => void;
  setLayerVisibility: (layer: keyof LayerVisibility, visible: boolean) => void;
  setStandColorMode: (mode: StandColorMode) => void;
  setOrtofotoOpacity: (opacity: number) => void;
  setBarkBeetleOpacity: (opacity: number) => void;
  setSoilMoistureOpacity: (opacity: number) => void;
  setContextMenu: (menu: { x: number; y: number; standId: string } | null) => void;
  pushUndo: (snapshot: string) => void;
  undo: () => string | undefined;
  redo: () => string | undefined;
  resetMapState: () => void;
}

const defaultLayers: LayerVisibility = {
  ortofoto: false,
  stands: true,
  standLabels: true,
  barkBeetle: false,
  soilMoisture: false,
  propertyBoundary: true,
};

export const useMapStore = create<MapState>((set, get) => ({
  mapCenter: [15.5, 59.3], // central Sweden default
  mapZoom: 12,
  selectedStandId: null,
  hoveredStandId: null,
  editingStandId: null,
  drawMode: false,
  drawType: null,
  layers: { ...defaultLayers },
  standColorMode: 'targetClass',
  ortofotoOpacity: 0.8,
  barkBeetleOpacity: 0.5,
  soilMoistureOpacity: 0.5,
  contextMenu: null,
  undoStack: [],
  redoStack: [],

  setMapCenter: (center) => set({ mapCenter: center }),
  setMapZoom: (zoom) => set({ mapZoom: zoom }),
  setSelectedStand: (id) => set({ selectedStandId: id }),
  setHoveredStand: (id) => set({ hoveredStandId: id }),
  setEditingStand: (id) => set({ editingStandId: id }),

  setDrawMode: (active, type) =>
    set({
      drawMode: active,
      drawType: active ? (type ?? 'polygon') : null,
      selectedStandId: active ? null : get().selectedStandId,
    }),

  toggleLayer: (layer) =>
    set((state) => ({
      layers: { ...state.layers, [layer]: !state.layers[layer] },
    })),

  setLayerVisibility: (layer, visible) =>
    set((state) => ({
      layers: { ...state.layers, [layer]: visible },
    })),

  setStandColorMode: (mode) => set({ standColorMode: mode }),
  setOrtofotoOpacity: (opacity) => set({ ortofotoOpacity: opacity }),
  setBarkBeetleOpacity: (opacity) => set({ barkBeetleOpacity: opacity }),
  setSoilMoistureOpacity: (opacity) => set({ soilMoistureOpacity: opacity }),
  setContextMenu: (menu) => set({ contextMenu: menu }),

  pushUndo: (snapshot) =>
    set((state) => ({
      undoStack: [...state.undoStack, snapshot],
      redoStack: [],
    })),

  undo: () => {
    const { undoStack, redoStack } = get();
    if (undoStack.length === 0) return undefined;
    const last = undoStack[undoStack.length - 1];
    set({
      undoStack: undoStack.slice(0, -1),
      redoStack: [...redoStack, last],
    });
    return last;
  },

  redo: () => {
    const { undoStack, redoStack } = get();
    if (redoStack.length === 0) return undefined;
    const last = redoStack[redoStack.length - 1];
    set({
      redoStack: redoStack.slice(0, -1),
      undoStack: [...undoStack, last],
    });
    return last;
  },

  resetMapState: () =>
    set({
      selectedStandId: null,
      hoveredStandId: null,
      editingStandId: null,
      drawMode: false,
      drawType: null,
      contextMenu: null,
      undoStack: [],
      redoStack: [],
    }),
}));
