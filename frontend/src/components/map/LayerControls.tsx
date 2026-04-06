import { useState } from 'react';
import { useMapStore, type StandColorMode } from '@/store/mapStore';
import { Layers, ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';

export default function LayerControls() {
  const [open, setOpen] = useState(true);
  const {
    layers,
    toggleLayer,
    standColorMode,
    setStandColorMode,
    ortofotoOpacity,
    setOrtofotoOpacity,
    barkBeetleOpacity,
    setBarkBeetleOpacity,
    soilMoistureOpacity,
    setSoilMoistureOpacity,
  } = useMapStore();

  const colorModes: { value: StandColorMode; label: string }[] = [
    { value: 'targetClass', label: 'Målklass' },
    { value: 'action', label: 'Åtgärd' },
    { value: 'age', label: 'Ålder' },
    { value: 'volume', label: 'Volym' },
  ];

  return (
    <div className="absolute right-3 top-3 z-20 w-64">
      {/* Toggle button */}
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between rounded-t-lg bg-white px-4 py-2.5 shadow-md hover:bg-gray-50"
      >
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-forest-700" />
          <span className="text-sm font-semibold text-gray-800">Lager</span>
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-gray-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-500" />
        )}
      </button>

      {/* Panel */}
      {open && (
        <div className="rounded-b-lg border-t border-gray-100 bg-white p-4 shadow-md space-y-4">
          {/* Layer toggles */}
          <div className="space-y-2">
            <LayerToggle
              label="Ortofoto"
              checked={layers.ortofoto}
              onChange={() => toggleLayer('ortofoto')}
            />
            {layers.ortofoto && (
              <OpacitySlider
                value={ortofotoOpacity}
                onChange={setOrtofotoOpacity}
              />
            )}

            <LayerToggle
              label="Avdelningar"
              checked={layers.stands}
              onChange={() => toggleLayer('stands')}
            />
            <LayerToggle
              label="Avdelningsetiketter"
              checked={layers.standLabels}
              onChange={() => toggleLayer('standLabels')}
            />
            <LayerToggle
              label="Fastighetsgräns"
              checked={layers.propertyBoundary}
              onChange={() => toggleLayer('propertyBoundary')}
            />

            <div className="border-t border-gray-100 pt-2" />

            <LayerToggle
              label="Barkborreindicering"
              checked={layers.barkBeetle}
              onChange={() => toggleLayer('barkBeetle')}
            />
            {layers.barkBeetle && (
              <OpacitySlider
                value={barkBeetleOpacity}
                onChange={setBarkBeetleOpacity}
              />
            )}

            <LayerToggle
              label="Markfuktighet"
              checked={layers.soilMoisture}
              onChange={() => toggleLayer('soilMoisture')}
            />
            {layers.soilMoisture && (
              <OpacitySlider
                value={soilMoistureOpacity}
                onChange={setSoilMoistureOpacity}
              />
            )}
          </div>

          {/* Color mode */}
          <div>
            <p className="mb-2 text-xs font-semibold text-gray-500 uppercase">Färglägg efter</p>
            <div className="grid grid-cols-2 gap-1">
              {colorModes.map((mode) => (
                <button
                  key={mode.value}
                  onClick={() => setStandColorMode(mode.value)}
                  className={clsx(
                    'rounded-md px-2.5 py-1.5 text-xs font-medium transition',
                    standColorMode === mode.value
                      ? 'bg-forest-700 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
                  )}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LayerToggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between">
      <span className="text-sm text-gray-700">{label}</span>
      <button
        role="switch"
        aria-checked={checked}
        onClick={onChange}
        className={clsx(
          'relative h-5 w-9 rounded-full transition-colors',
          checked ? 'bg-forest-600' : 'bg-gray-300',
        )}
      >
        <span
          className={clsx(
            'absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform',
            checked && 'translate-x-4',
          )}
        />
      </button>
    </label>
  );
}

function OpacitySlider({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-2 pl-2">
      <span className="text-xs text-gray-500">Opacitet</span>
      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-gray-200 accent-forest-600"
      />
      <span className="w-8 text-right text-xs text-gray-500">
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}
