import { useCallback, useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { useMapStore } from '@/store/mapStore';
import { usePropertyStore } from '@/store/propertyStore';
import {
  Pentagon,
  MousePointer2,
  Pencil,
  Scissors,
  Trash2,
  Undo2,
  Redo2,
} from 'lucide-react';
import clsx from 'clsx';

interface DrawToolsProps {
  map: maplibregl.Map | null;
  propertyId: string;
}

type DrawToolMode = 'select' | 'draw_polygon' | 'edit' | 'split' | 'delete';

export default function DrawTools({ map, propertyId }: DrawToolsProps) {
  const { drawMode, setDrawMode, undo, redo } = useMapStore();
  const { createStand } = usePropertyStore();
  const [activeTool, setActiveTool] = useState<DrawToolMode>('select');
  const drawPointsRef = useRef<[number, number][]>([]);
  const drawSourceAdded = useRef(false);

  /* ── Setup draw layer ── */
  useEffect(() => {
    if (!map) return;

    const onLoad = () => {
      if (drawSourceAdded.current) return;
      if (map.getSource('draw-polygon')) return;

      map.addSource('draw-polygon', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map.addLayer({
        id: 'draw-polygon-fill',
        type: 'fill',
        source: 'draw-polygon',
        paint: {
          'fill-color': '#3b82f6',
          'fill-opacity': 0.2,
        },
      });
      map.addLayer({
        id: 'draw-polygon-line',
        type: 'line',
        source: 'draw-polygon',
        paint: {
          'line-color': '#3b82f6',
          'line-width': 2,
          'line-dasharray': [3, 2],
        },
      });
      map.addLayer({
        id: 'draw-polygon-points',
        type: 'circle',
        source: 'draw-polygon',
        filter: ['==', '$type', 'Point'],
        paint: {
          'circle-radius': 5,
          'circle-color': '#3b82f6',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
        },
      });
      drawSourceAdded.current = true;
    };

    if (map.loaded()) {
      onLoad();
    } else {
      map.on('load', onLoad);
    }
  }, [map]);

  /* ── Update draw polygon on the map ── */
  const updateDrawGeometry = useCallback(() => {
    if (!map) return;
    const source = map.getSource('draw-polygon') as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    const points = drawPointsRef.current;
    const features: GeoJSON.Feature[] = [];

    // Add vertex points
    points.forEach((p) => {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: p },
        properties: {},
      });
    });

    // Add polygon if 3+ points
    if (points.length >= 3) {
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [[...points, points[0]]],
        },
        properties: {},
      });
    } else if (points.length >= 2) {
      // Add line if 2 points
      features.push({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: points,
        },
        properties: {},
      });
    }

    source.setData({ type: 'FeatureCollection', features });
  }, [map]);

  /* ── Click handler for draw mode ── */
  useEffect(() => {
    if (!map || activeTool !== 'draw_polygon' || !drawMode) return;

    const onClick = (e: maplibregl.MapMouseEvent) => {
      drawPointsRef.current.push([e.lngLat.lng, e.lngLat.lat]);
      updateDrawGeometry();
    };

    const onDblClick = async (e: maplibregl.MapMouseEvent) => {
      e.preventDefault();
      const points = drawPointsRef.current;
      if (points.length < 3) return;

      const polygon: GeoJSON.Polygon = {
        type: 'Polygon',
        coordinates: [[...points, points[0]]],
      };

      try {
        await createStand(propertyId, {
          geometry: polygon,
          standNumber: Date.now() % 1000, // placeholder
          targetClass: 'PG',
          areaHa: null,
          siteIndex: null,
          ageYears: null,
          volumeM3PerHa: null,
          totalVolumeM3: null,
          basalAreaM2: null,
          meanHeightM: null,
          meanDiameterCm: null,
          pinePct: 0,
          sprucePct: 0,
          deciduousPct: 0,
          contortaPct: 0,
          proposedAction: null,
          actionUrgency: null,
          actionYear: null,
          notes: null,
        });
      } catch {
        // error handled in store
      }

      // Clear drawing
      drawPointsRef.current = [];
      updateDrawGeometry();
    };

    map.on('click', onClick);
    map.on('dblclick', onDblClick);
    map.getCanvas().style.cursor = 'crosshair';

    return () => {
      map.off('click', onClick);
      map.off('dblclick', onDblClick);
      map.getCanvas().style.cursor = '';
    };
  }, [map, activeTool, drawMode, updateDrawGeometry, createStand, propertyId]);

  /* ── Tool selection ── */
  const selectTool = (tool: DrawToolMode) => {
    setActiveTool(tool);
    if (tool === 'select') {
      setDrawMode(false);
      drawPointsRef.current = [];
      updateDrawGeometry();
    } else {
      setDrawMode(true, tool === 'split' ? 'line' : 'polygon');
    }
  };

  const tools: { mode: DrawToolMode; icon: React.ReactNode; label: string }[] = [
    { mode: 'select', icon: <MousePointer2 className="h-4 w-4" />, label: 'Välj' },
    { mode: 'draw_polygon', icon: <Pentagon className="h-4 w-4" />, label: 'Rita polygon' },
    { mode: 'edit', icon: <Pencil className="h-4 w-4" />, label: 'Redigera gräns' },
    { mode: 'split', icon: <Scissors className="h-4 w-4" />, label: 'Dela avdelning' },
    { mode: 'delete', icon: <Trash2 className="h-4 w-4" />, label: 'Radera' },
  ];

  return (
    <div className="absolute left-3 top-3 z-20 flex flex-col gap-1 rounded-lg bg-white p-1.5 shadow-md">
      {tools.map((tool) => (
        <button
          key={tool.mode}
          onClick={() => selectTool(tool.mode)}
          className={clsx(
            'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition',
            activeTool === tool.mode
              ? 'bg-forest-700 text-white'
              : 'text-gray-700 hover:bg-gray-100',
          )}
          title={tool.label}
        >
          {tool.icon}
          <span className="hidden xl:inline">{tool.label}</span>
        </button>
      ))}

      <div className="my-1 border-t border-gray-200" />

      {/* Undo / Redo */}
      <button
        onClick={() => undo()}
        className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100"
        title="Ångra"
      >
        <Undo2 className="h-4 w-4" />
      </button>
      <button
        onClick={() => redo()}
        className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-gray-700 hover:bg-gray-100"
        title="Gör om"
      >
        <Redo2 className="h-4 w-4" />
      </button>

      {/* Drawing instructions */}
      {drawMode && activeTool === 'draw_polygon' && (
        <div className="mt-2 max-w-[180px] rounded bg-forest-50 p-2 text-xs text-forest-800">
          Klicka för att placera punkter. Dubbelklicka för att avsluta polygonen.
        </div>
      )}
    </div>
  );
}
