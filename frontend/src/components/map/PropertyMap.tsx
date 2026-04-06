import { useEffect, useRef, useCallback, useState } from 'react';
import { useParams } from 'react-router-dom';
import maplibregl from 'maplibre-gl';
import * as turf from '@turf/turf';
import { usePropertyStore } from '@/store/propertyStore';
import { useMapStore, type StandColorMode } from '@/store/mapStore';
import LayerControls from './LayerControls';
import DrawTools from './DrawTools';
import StandPanel from '@/components/stands/StandPanel';
import StandTable from '@/components/stands/StandTable';
import ActionsView from '@/components/property/ActionsView';
import EconomyView from '@/components/property/EconomyView';
import PlanView from '@/components/property/PlanView';
import { useSearchParams } from 'react-router-dom';
import clsx from 'clsx';

/* ───────── Color helpers ───────── */

function getTargetClassColor(tc: string): string {
  switch (tc) {
    case 'PG': return '#22c55e';
    case 'PF': return '#3b82f6';
    case 'NS': return '#eab308';
    case 'NO': return '#f97316';
    case 'K':  return '#a855f7';
    default:   return '#6b7280';
  }
}

function getActionColor(action: string): string {
  switch (action) {
    case 'slutavverkning': return '#dc2626';
    case 'gallring':       return '#f59e0b';
    case 'rojargardering': return '#84cc16';
    case 'plantering':     return '#06b6d4';
    case 'markberedning':  return '#8b5cf6';
    case 'naturvard':      return '#10b981';
    case 'ingen':          return '#d1d5db';
    default:               return '#6b7280';
  }
}

function getAgeColor(age: number): string {
  if (age < 20) return '#bbf7d0';
  if (age < 40) return '#86efac';
  if (age < 60) return '#4ade80';
  if (age < 80) return '#22c55e';
  if (age < 100) return '#16a34a';
  if (age < 120) return '#15803d';
  return '#14532d';
}

function getVolumeColor(vol: number): string {
  if (vol < 50) return '#fef9c3';
  if (vol < 100) return '#fde68a';
  if (vol < 150) return '#fbbf24';
  if (vol < 200) return '#f59e0b';
  if (vol < 300) return '#d97706';
  if (vol < 400) return '#b45309';
  return '#92400e';
}

function buildFillColor(mode: StandColorMode): maplibregl.ExpressionSpecification {
  switch (mode) {
    case 'targetClass':
      return [
        'match', ['get', 'targetClass'],
        'PG', getTargetClassColor('PG'),
        'PF', getTargetClassColor('PF'),
        'NS', getTargetClassColor('NS'),
        'NO', getTargetClassColor('NO'),
        'K',  getTargetClassColor('K'),
        '#6b7280',
      ];
    case 'action':
      return [
        'match', ['get', 'proposedAction'],
        'slutavverkning', getActionColor('slutavverkning'),
        'gallring',       getActionColor('gallring'),
        'rojargardering', getActionColor('rojargardering'),
        'plantering',     getActionColor('plantering'),
        'markberedning',  getActionColor('markberedning'),
        'naturvard',      getActionColor('naturvard'),
        'ingen',          getActionColor('ingen'),
        '#6b7280',
      ];
    case 'age':
      return [
        'interpolate', ['linear'], ['get', 'ageYears'],
        0,   getAgeColor(0),
        20,  getAgeColor(20),
        40,  getAgeColor(40),
        60,  getAgeColor(60),
        80,  getAgeColor(80),
        100, getAgeColor(100),
        140, getAgeColor(140),
      ];
    case 'volume':
      return [
        'interpolate', ['linear'], ['get', 'volumeM3PerHa'],
        0,   getVolumeColor(0),
        50,  getVolumeColor(50),
        100, getVolumeColor(100),
        200, getVolumeColor(200),
        300, getVolumeColor(300),
        400, getVolumeColor(400),
      ];
  }
}

/* ───────── Main component ───────── */

export default function PropertyMap() {
  const { id: propertyId } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const tab = searchParams.get('tab');

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [cursorCoords, setCursorCoords] = useState<{ lng: number; lat: number } | null>(null);

  const { currentProperty, fetchProperty, fetchStands, stands } = usePropertyStore();
  const {
    selectedStandId,
    setSelectedStand,
    setHoveredStand,
    layers,
    standColorMode,
    ortofotoOpacity,
    contextMenu,
    setContextMenu,
    drawMode,
  } = useMapStore();

  /* Load property + stands */
  useEffect(() => {
    if (propertyId) {
      fetchProperty(propertyId);
      fetchStands(propertyId);
    }
  }, [propertyId, fetchProperty, fetchStands]);

  /* ── Init map ── */
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '&copy; OpenStreetMap contributors',
          },
        },
        layers: [
          {
            id: 'osm-tiles',
            type: 'raster',
            source: 'osm',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: [15.5, 59.3],
      zoom: 12,
      attributionControl: { compact: true },
    });

    map.addControl(new maplibregl.NavigationControl(), 'bottom-right');
    map.addControl(
      new maplibregl.ScaleControl({ maxWidth: 200, unit: 'metric' }),
      'bottom-left',
    );

    map.on('load', () => {
      setMapLoaded(true);

      /* ── Ortofoto (Lantmäteriet WMS) ── */
      map.addSource('ortofoto', {
        type: 'raster',
        tiles: [
          'https://minkarta.lantmateriet.se/map/ortofoto/?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=Ortofoto_0.5&STYLES=&CRS=EPSG:3857&BBOX={bbox-epsg-3857}&WIDTH=256&HEIGHT=256&FORMAT=image/jpeg',
        ],
        tileSize: 256,
      });
      map.addLayer(
        {
          id: 'ortofoto-layer',
          type: 'raster',
          source: 'ortofoto',
          layout: { visibility: 'none' },
          paint: { 'raster-opacity': 0.8 },
        },
        'osm-tiles',
      );

      /* ── Stands source (empty initially) ── */
      map.addSource('stands', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      // Stand fill
      map.addLayer({
        id: 'stands-fill',
        type: 'fill',
        source: 'stands',
        paint: {
          'fill-color': buildFillColor('targetClass'),
          'fill-opacity': [
            'case',
            ['boolean', ['feature-state', 'selected'], false], 0.7,
            ['boolean', ['feature-state', 'hover'], false], 0.55,
            0.4,
          ],
        },
      });

      // Stand outline
      map.addLayer({
        id: 'stands-outline',
        type: 'line',
        source: 'stands',
        paint: {
          'line-color': [
            'case',
            ['boolean', ['feature-state', 'selected'], false], '#ffffff',
            '#374151',
          ],
          'line-width': [
            'case',
            ['boolean', ['feature-state', 'selected'], false], 3,
            1.5,
          ],
        },
      });

      // Stand labels
      map.addLayer({
        id: 'stands-labels',
        type: 'symbol',
        source: 'stands',
        layout: {
          'text-field': ['concat', ['to-string', ['get', 'standNumber']], '\n', ['to-string', ['get', 'volumeM3PerHa']], ' m\u00b3'],
          'text-size': 12,
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
          'text-anchor': 'center',
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': '#1f2937',
          'text-halo-color': '#ffffff',
          'text-halo-width': 1.5,
        },
      });

      /* ── Property boundary ── */
      map.addSource('property-boundary', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map.addLayer({
        id: 'property-boundary-line',
        type: 'line',
        source: 'property-boundary',
        paint: {
          'line-color': '#dc2626',
          'line-width': 2.5,
          'line-dasharray': [4, 3],
        },
      });

      /* ── Bark beetle risk overlay ── */
      map.addSource('barkbeetle', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map.addLayer({
        id: 'barkbeetle-fill',
        type: 'fill',
        source: 'barkbeetle',
        layout: { visibility: 'none' },
        paint: {
          'fill-color': [
            'interpolate', ['linear'], ['get', 'riskScore'],
            0, 'rgba(255,255,0,0.1)',
            50, 'rgba(255,165,0,0.3)',
            100, 'rgba(255,0,0,0.5)',
          ],
          'fill-opacity': 0.5,
        },
      });

      /* ── Soil moisture overlay ── */
      map.addSource('soilmoisture', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map.addLayer({
        id: 'soilmoisture-fill',
        type: 'fill',
        source: 'soilmoisture',
        layout: { visibility: 'none' },
        paint: {
          'fill-color': [
            'interpolate', ['linear'], ['get', 'moistureIndex'],
            0, 'rgba(255,235,59,0.1)',
            50, 'rgba(33,150,243,0.3)',
            100, 'rgba(13,71,161,0.5)',
          ],
          'fill-opacity': 0.5,
        },
      });
    });

    /* ── Click handler ── */
    map.on('click', 'stands-fill', (e) => {
      if (drawMode) return;
      const feature = e.features?.[0];
      if (feature?.properties?.id) {
        setSelectedStand(feature.properties.id as string);
      }
    });

    /* ── Hover handler ── */
    let hoveredId: string | null = null;
    map.on('mousemove', 'stands-fill', (e) => {
      if (e.features && e.features.length > 0) {
        const fid = e.features[0].id as string;
        if (hoveredId && hoveredId !== fid) {
          map.setFeatureState({ source: 'stands', id: hoveredId }, { hover: false });
        }
        hoveredId = fid;
        map.setFeatureState({ source: 'stands', id: fid }, { hover: true });
        setHoveredStand(e.features[0].properties?.id as string);
        map.getCanvas().style.cursor = 'pointer';
      }
    });
    map.on('mouseleave', 'stands-fill', () => {
      if (hoveredId) {
        map.setFeatureState({ source: 'stands', id: hoveredId }, { hover: false });
        hoveredId = null;
      }
      setHoveredStand(null);
      map.getCanvas().style.cursor = '';
    });

    /* ── Context menu ── */
    map.on('contextmenu', 'stands-fill', (e) => {
      e.preventDefault();
      const feature = e.features?.[0];
      if (feature?.properties?.id) {
        setContextMenu({
          x: e.point.x,
          y: e.point.y,
          standId: feature.properties.id as string,
        });
      }
    });

    /* ── Cursor coords ── */
    map.on('mousemove', (e) => {
      setCursorCoords({ lng: e.lngLat.lng, lat: e.lngLat.lat });
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── Update stands data ── */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const source = map.getSource('stands') as maplibregl.GeoJSONSource | undefined;
    if (source) {
      // Add numeric id for feature-state
      const withIds = {
        ...stands,
        features: stands.features.map((f, i) => ({ ...f, id: i })),
      };
      source.setData(withIds as GeoJSON.FeatureCollection);
    }

    // Fly to stands extent
    if (stands.features.length > 0) {
      try {
        const bbox = turf.bbox(stands) as [number, number, number, number];
        map.fitBounds(bbox, { padding: 60, maxZoom: 15, duration: 1000 });
      } catch {
        // ignore bbox errors
      }
    }
  }, [stands, mapLoaded]);

  /* ── Update property boundary ── */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !currentProperty?.boundaryGeojson) return;

    const source = map.getSource('property-boundary') as maplibregl.GeoJSONSource | undefined;
    if (source) {
      source.setData(currentProperty.boundaryGeojson);
    }

    // If no stands loaded yet, fit map to property boundary so the user sees the right area
    if (stands.features.length === 0) {
      try {
        const bbox = turf.bbox(currentProperty.boundaryGeojson) as [number, number, number, number];
        map.fitBounds(bbox, { padding: 60, maxZoom: 14, duration: 1000 });
      } catch {
        // ignore bbox errors
      }
    }
  }, [currentProperty, mapLoaded, stands.features.length]);

  /* ── Layer visibility ── */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const setVis = (layerId: string, visible: boolean) => {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
      }
    };

    setVis('ortofoto-layer', layers.ortofoto);
    setVis('stands-fill', layers.stands);
    setVis('stands-outline', layers.stands);
    setVis('stands-labels', layers.standLabels);
    setVis('barkbeetle-fill', layers.barkBeetle);
    setVis('soilmoisture-fill', layers.soilMoisture);
    setVis('property-boundary-line', layers.propertyBoundary);
  }, [layers, mapLoaded]);

  /* ── Ortofoto opacity ── */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;
    if (map.getLayer('ortofoto-layer')) {
      map.setPaintProperty('ortofoto-layer', 'raster-opacity', ortofotoOpacity);
    }
  }, [ortofotoOpacity, mapLoaded]);

  /* ── Stand color mode ── */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;
    if (map.getLayer('stands-fill')) {
      map.setPaintProperty('stands-fill', 'fill-color', buildFillColor(standColorMode));
    }
  }, [standColorMode, mapLoaded]);

  /* ── Selected stand highlight ── */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    // Clear all previous selections
    stands.features.forEach((_, i) => {
      map.setFeatureState({ source: 'stands', id: i }, { selected: false });
    });

    // Set new selection
    if (selectedStandId) {
      const idx = stands.features.findIndex((f) => f.properties.id === selectedStandId);
      if (idx >= 0) {
        map.setFeatureState({ source: 'stands', id: idx }, { selected: true });
      }
    }
  }, [selectedStandId, stands, mapLoaded]);

  /* ── Close context menu on map click ── */
  const handleMapClick = useCallback(() => {
    if (contextMenu) setContextMenu(null);
  }, [contextMenu, setContextMenu]);

  /* ── Context menu actions ── */
  const handleContextAction = useCallback(
    (action: string) => {
      if (!contextMenu) return;
      switch (action) {
        case 'edit':
          setSelectedStand(contextMenu.standId);
          break;
        case 'delete':
          if (propertyId) {
            usePropertyStore.getState().deleteStand(propertyId, contextMenu.standId);
          }
          break;
      }
      setContextMenu(null);
    },
    [contextMenu, setContextMenu, setSelectedStand, propertyId],
  );

  // Tab views (non-map tabs)
  if (tab === 'stands') {
    return (
      <div className="p-6">
        <StandTable propertyId={propertyId!} />
      </div>
    );
  }

  if (tab === 'actions') {
    return (
      <div className="p-6">
        <ActionsView propertyId={propertyId!} />
      </div>
    );
  }

  if (tab === 'economy') {
    return (
      <div className="p-6">
        <EconomyView propertyId={propertyId!} />
      </div>
    );
  }

  if (tab === 'plan') {
    return (
      <div className="p-6">
        <PlanView propertyId={propertyId!} />
      </div>
    );
  }

  return (
    <div className="relative flex h-full" onClick={handleMapClick}>
      {/* Map container */}
      <div ref={mapContainerRef} className="flex-1" />

      {/* Layer controls (top-right) */}
      <LayerControls />

      {/* Draw tools (top-left) */}
      <DrawTools map={mapRef.current} propertyId={propertyId!} />

      {/* Stand panel (right side) */}
      {selectedStandId && !drawMode && (
        <StandPanel
          propertyId={propertyId!}
          standId={selectedStandId}
          onClose={() => setSelectedStand(null)}
        />
      )}

      {/* Cursor coordinates (bottom-left, above scale) */}
      {cursorCoords && (
        <div className="absolute bottom-10 left-2 z-10 rounded bg-white/90 px-2 py-1 text-xs font-mono text-gray-600 shadow">
          {cursorCoords.lat.toFixed(5)}, {cursorCoords.lng.toFixed(5)}
        </div>
      )}

      {/* Context menu */}
      {contextMenu && (
        <div
          className="absolute z-50 w-48 rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            className="flex w-full items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            onClick={() => handleContextAction('edit')}
          >
            Redigera avdelning
          </button>
          <button
            className="flex w-full items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            onClick={() => handleContextAction('split')}
          >
            Dela avdelning
          </button>
          <button
            className="flex w-full items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            onClick={() => handleContextAction('merge')}
          >
            Sammanfoga avdelningar
          </button>
          <div className="my-1 border-t border-gray-100" />
          <button
            className="flex w-full items-center px-4 py-2 text-sm text-red-600 hover:bg-red-50"
            onClick={() => handleContextAction('delete')}
          >
            Ta bort avdelning
          </button>
        </div>
      )}

      {/* Legend */}
      <div className={clsx(
        'absolute bottom-10 right-2 z-10 rounded-lg bg-white/95 p-3 shadow-md',
        selectedStandId && 'right-[420px]',
      )}>
        <p className="mb-2 text-xs font-semibold text-gray-600 uppercase">
          {standColorMode === 'targetClass' && 'Målklass'}
          {standColorMode === 'action' && 'Åtgärd'}
          {standColorMode === 'age' && 'Ålder'}
          {standColorMode === 'volume' && 'Volym'}
        </p>
        {standColorMode === 'targetClass' && (
          <div className="space-y-1">
            {(['PG', 'PF', 'NS', 'NO', 'K'] as const).map((tc) => (
              <div key={tc} className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: getTargetClassColor(tc) }} />
                <span className="text-xs text-gray-700">{tc}</span>
              </div>
            ))}
          </div>
        )}
        {standColorMode === 'action' && (
          <div className="space-y-1">
            {[
              ['slutavverkning', 'Slutavverkning'],
              ['gallring', 'Gallring'],
              ['rojargardering', 'Röjning'],
              ['plantering', 'Plantering'],
              ['naturvard', 'Naturvård'],
              ['ingen', 'Ingen'],
            ].map(([key, label]) => (
              <div key={key} className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: getActionColor(key) }} />
                <span className="text-xs text-gray-700">{label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
