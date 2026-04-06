import { useState, useEffect, useRef, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import { useForm, useFieldArray } from 'react-hook-form';
import { useGeolocation } from '@/hooks/useGeolocation';
import { useOfflineSync } from '@/hooks/useOfflineSync';
import { useAuthStore } from '@/store/authStore';
import { fieldDataApi } from '@/services/api';
import type { FieldData, SampleTree, SoilMoisture } from '@/types';
import {
  MapPin,
  Plus,
  Trash2,
  Camera,
  Save,
  ChevronUp,
  ChevronDown,
  Wifi,
  WifiOff,
  ArrowLeft,
  Crosshair,
  List,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';

interface FieldFormData {
  relascopeValue: number;
  sampleTrees: SampleTree[];
  soilMoisture: SoilMoisture;
  hasDeadWood: boolean;
  hasOldTrees: boolean;
  isKeyBiotope: boolean;
  waterProximity: boolean;
  notes: string;
}

export default function FieldApp() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const [sheetExpanded, setSheetExpanded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [photos, setPhotos] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [savedEntries, setSavedEntries] = useState<FieldData[]>([]);

  const { latitude, longitude, accuracy } = useGeolocation();
  const { isOnline, pendingCount, saveOffline, sync } = useOfflineSync();
  const user = useAuthStore((s) => s.user);

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<FieldFormData>({
    defaultValues: {
      relascopeValue: 0,
      sampleTrees: [],
      soilMoisture: 'frisk',
      hasDeadWood: false,
      hasOldTrees: false,
      isKeyBiotope: false,
      waterProximity: false,
      notes: '',
    },
  });

  const { fields: treeFields, append: addTree, remove: removeTree } = useFieldArray({
    control,
    name: 'sampleTrees',
  });

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
            attribution: '&copy; OpenStreetMap',
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
      zoom: 15,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  /* ── Update GPS marker ── */
  useEffect(() => {
    if (!mapRef.current || !latitude || !longitude) return;

    if (!markerRef.current) {
      const el = document.createElement('div');
      el.className = 'gps-marker';
      el.style.width = '20px';
      el.style.height = '20px';
      el.style.borderRadius = '50%';
      el.style.backgroundColor = '#3b82f6';
      el.style.border = '3px solid white';
      el.style.boxShadow = '0 0 0 4px rgba(59,130,246,0.3), 0 2px 6px rgba(0,0,0,0.3)';

      markerRef.current = new maplibregl.Marker({ element: el })
        .setLngLat([longitude, latitude])
        .addTo(mapRef.current);

      mapRef.current.flyTo({ center: [longitude, latitude], zoom: 16, duration: 1000 });
    } else {
      markerRef.current.setLngLat([longitude, latitude]);
    }
  }, [latitude, longitude]);

  /* ── Center on GPS ── */
  const centerOnGps = useCallback(() => {
    if (mapRef.current && latitude && longitude) {
      mapRef.current.flyTo({ center: [longitude, latitude], zoom: 17, duration: 800 });
    }
  }, [latitude, longitude]);

  /* ── Photo capture ── */
  const handlePhotoCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setPhotos((prev) => [...prev, ...Array.from(e.target.files!)]);
    }
  };

  /* ── Submit ── */
  const onSubmit = async (data: FieldFormData) => {
    if (!latitude || !longitude || !user) return;

    setSubmitting(true);

    const entry: Omit<FieldData, 'id'> = {
      standId: '', // determined by backend based on GPS
      recordedBy: user.name,
      recordedAt: new Date().toISOString(),
      gpsLat: latitude,
      gpsLon: longitude,
      relascopeValue: data.relascopeValue,
      sampleTrees: data.sampleTrees,
      soilMoisture: data.soilMoisture,
      natureValues: {
        hasDeadWood: data.hasDeadWood,
        hasOldTrees: data.hasOldTrees,
        isKeyBiotope: data.isKeyBiotope,
        waterProximity: data.waterProximity,
      },
      photos: [],
      notes: data.notes,
    };

    try {
      if (isOnline) {
        // Upload photos first
        const uploadedPhotos: string[] = [];
        for (const photo of photos) {
          const { url } = await fieldDataApi.uploadPhoto(photo);
          uploadedPhotos.push(url);
        }
        entry.photos = uploadedPhotos;
        const saved = await fieldDataApi.create(entry.standId, entry);
        setSavedEntries((prev) => [saved, ...prev]);
      } else {
        await saveOffline(entry);
      }

      reset();
      setPhotos([]);
      setSheetExpanded(false);
    } catch {
      // If network error, save offline
      await saveOffline(entry);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex h-screen flex-col">
      {/* Top bar */}
      <header className="absolute left-0 right-0 top-0 z-20 flex items-center justify-between bg-white/95 px-3 py-2 shadow-sm backdrop-blur">
        <Link to="/" className="rounded-md p-2 text-gray-600 hover:bg-gray-100">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-sm font-bold text-forest-800">Fältapp</h1>
        <div className="flex items-center gap-2">
          {/* Online/Offline indicator */}
          <div className={clsx(
            'flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium',
            isOnline ? 'bg-green-100 text-green-800' : 'bg-orange-100 text-orange-800',
          )}>
            {isOnline ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
            {isOnline ? 'Online' : `Offline (${pendingCount})`}
          </div>
          {!isOnline && pendingCount > 0 && (
            <button
              onClick={sync}
              className="rounded bg-forest-700 px-2 py-1 text-xs text-white"
            >
              Synka
            </button>
          )}
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="rounded-md p-2 text-gray-600 hover:bg-gray-100"
          >
            <List className="h-5 w-5" />
          </button>
        </div>
      </header>

      {/* Map */}
      <div ref={mapContainerRef} className="flex-1" />

      {/* Center on GPS button */}
      <button
        onClick={centerOnGps}
        className="absolute right-3 top-20 z-20 rounded-full bg-white p-2.5 shadow-lg hover:bg-gray-50"
      >
        <Crosshair className="h-5 w-5 text-blue-600" />
      </button>

      {/* GPS accuracy indicator */}
      {latitude && (
        <div className="absolute left-3 top-14 z-20 rounded-full bg-white/90 px-3 py-1 text-xs shadow">
          <MapPin className="mr-1 inline h-3 w-3 text-blue-600" />
          {accuracy ? `\u00b1${Math.round(accuracy)} m` : 'GPS aktiv'}
        </div>
      )}

      {/* History panel */}
      {showHistory && (
        <div className="absolute inset-x-0 bottom-0 top-12 z-30 overflow-y-auto bg-white p-4">
          <h2 className="mb-3 text-lg font-bold text-gray-800">Tidigare observationer</h2>
          {savedEntries.length === 0 ? (
            <p className="text-sm text-gray-500">Inga observationer ännu</p>
          ) : (
            <div className="space-y-3">
              {savedEntries.map((entry) => (
                <div key={entry.id} className="rounded-lg border border-gray-200 p-3">
                  <div className="flex justify-between">
                    <span className="text-sm font-medium">Relaskop: {entry.relascopeValue}</span>
                    <span className="text-xs text-gray-500">
                      {new Date(entry.recordedAt).toLocaleString('sv-SE')}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    {(entry.sampleTrees ?? []).length} provträd &middot;
                    Markfukt: {entry.soilMoisture}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Bottom sheet */}
      <div
        className={clsx(
          'absolute inset-x-0 bottom-0 z-20 rounded-t-2xl bg-white shadow-[0_-4px_20px_rgba(0,0,0,0.15)] transition-all duration-300',
          sheetExpanded ? 'top-12' : 'h-auto',
        )}
      >
        {/* Sheet handle */}
        <button
          onClick={() => setSheetExpanded(!sheetExpanded)}
          className="flex w-full items-center justify-center pb-1 pt-3"
        >
          <div className="h-1 w-10 rounded-full bg-gray-300" />
        </button>

        <div className="flex items-center justify-between px-4 pb-2">
          <h2 className="text-sm font-bold text-gray-800">Ny observation</h2>
          <button onClick={() => setSheetExpanded(!sheetExpanded)}>
            {sheetExpanded ? (
              <ChevronDown className="h-5 w-5 text-gray-500" />
            ) : (
              <ChevronUp className="h-5 w-5 text-gray-500" />
            )}
          </button>
        </div>

        {/* Form */}
        {sheetExpanded && (
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="space-y-4 overflow-y-auto px-4 pb-6"
            style={{ maxHeight: 'calc(100vh - 120px)' }}
          >
            {/* Relascope */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Relaskopvärde
              </label>
              <input
                type="number"
                step="any"
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-forest-500 focus:outline-none focus:ring-2 focus:ring-forest-500/20"
                placeholder="0"
                {...register('relascopeValue', { valueAsNumber: true, required: 'Krävs' })}
              />
              {errors.relascopeValue && (
                <p className="mt-1 text-xs text-red-600">{errors.relascopeValue.message}</p>
              )}
            </div>

            {/* Sample trees */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700">Provträd</label>
                <button
                  type="button"
                  onClick={() => addTree({ species: 'tall', diameter: 0, height: 0 })}
                  className="flex items-center gap-1 rounded-md bg-forest-50 px-2 py-1 text-xs font-medium text-forest-700 hover:bg-forest-100"
                >
                  <Plus className="h-3 w-3" />
                  Lägg till
                </button>
              </div>
              <div className="space-y-2">
                {treeFields.map((field, index) => (
                  <div key={field.id} className="flex items-center gap-2 rounded-lg bg-gray-50 p-2">
                    <select
                      className="rounded border border-gray-300 px-2 py-1.5 text-xs"
                      {...register(`sampleTrees.${index}.species`)}
                    >
                      <option value="tall">Tall</option>
                      <option value="gran">Gran</option>
                      <option value="bjork">Björk</option>
                      <option value="ovrig">Övrig</option>
                    </select>
                    <input
                      type="number"
                      step="0.1"
                      placeholder="Diam cm"
                      className="w-20 rounded border border-gray-300 px-2 py-1.5 text-xs"
                      {...register(`sampleTrees.${index}.diameter`, { valueAsNumber: true })}
                    />
                    <input
                      type="number"
                      step="0.1"
                      placeholder="Höjd m"
                      className="w-20 rounded border border-gray-300 px-2 py-1.5 text-xs"
                      {...register(`sampleTrees.${index}.height`, { valueAsNumber: true })}
                    />
                    <button
                      type="button"
                      onClick={() => removeTree(index)}
                      className="rounded p-1 text-red-500 hover:bg-red-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Soil moisture */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Markfuktighet
              </label>
              <select
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-forest-500 focus:outline-none focus:ring-2 focus:ring-forest-500/20"
                {...register('soilMoisture')}
              >
                <option value="torr">Torr</option>
                <option value="frisk">Frisk</option>
                <option value="fuktig">Fuktig</option>
                <option value="blot">Blöt</option>
              </select>
            </div>

            {/* Nature values */}
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Naturvärden</label>
              <div className="space-y-2">
                {[
                  { name: 'hasDeadWood' as const, label: 'Död ved' },
                  { name: 'hasOldTrees' as const, label: 'Gamla träd' },
                  { name: 'isKeyBiotope' as const, label: 'Nyckelbiotop' },
                  { name: 'waterProximity' as const, label: 'Nära vatten' },
                ].map((item) => (
                  <label key={item.name} className="flex items-center gap-2.5">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-gray-300 text-forest-600 focus:ring-forest-500"
                      {...register(item.name)}
                    />
                    <span className="text-sm text-gray-700">{item.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Photo */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Foto</label>
              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-300 px-4 py-3 text-sm text-gray-500 hover:border-forest-400 hover:text-forest-700">
                <Camera className="h-5 w-5" />
                Ta foto eller välj bild
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={handlePhotoCapture}
                  multiple
                />
              </label>
              {photos.length > 0 && (
                <p className="mt-1 text-xs text-gray-500">{photos.length} foto vald(a)</p>
              )}
            </div>

            {/* Notes */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Anteckningar</label>
              <textarea
                rows={3}
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-forest-500 focus:outline-none focus:ring-2 focus:ring-forest-500/20"
                placeholder="Övriga observationer..."
                {...register('notes')}
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={submitting || !latitude}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-forest-700 px-4 py-3 text-sm font-semibold text-white hover:bg-forest-800 disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {submitting ? 'Sparar...' : isOnline ? 'Spara observation' : 'Spara lokalt'}
            </button>
          </form>
        )}

        {/* Collapsed mini form */}
        {!sheetExpanded && (
          <div className="flex items-center gap-3 px-4 pb-4">
            <div className="flex-1">
              <input
                type="number"
                step="any"
                placeholder="Relaskopvärde"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                {...register('relascopeValue', { valueAsNumber: true })}
              />
            </div>
            <button
              type="button"
              onClick={() => setSheetExpanded(true)}
              className="rounded-lg bg-forest-700 px-4 py-2 text-sm font-medium text-white"
            >
              Mer
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
