import { useState, useEffect, useMemo } from 'react';
import { usePropertyStore } from '@/store/propertyStore';
import { geodataApi, fieldDataApi } from '@/services/api';
import { useForm } from 'react-hook-form';
import SpeciesChart from './SpeciesChart';
import { formatArea, formatVolume, formatCurrency } from '@/utils/formatters';
import type { Stand, StandFeature, FieldData, ForestData, TargetClass } from '@/types';
import {
  X,
  ChevronDown,
  Save,
  RefreshCw,
  TreePine,
  Mountain,
  DollarSign,
  Clipboard,
  MapPin,
} from 'lucide-react';
import clsx from 'clsx';

interface StandPanelProps {
  propertyId: string;
  standId: string;
  onClose: () => void;
}

type Tab = 'overview' | 'forestdata' | 'actions' | 'economy' | 'fielddata';

const TARGET_CLASS_COLORS: Record<TargetClass, string> = {
  PG: 'bg-green-100 text-green-800',
  PF: 'bg-blue-100 text-blue-800',
  NS: 'bg-yellow-100 text-yellow-800',
  NO: 'bg-orange-100 text-orange-800',
  K: 'bg-purple-100 text-purple-800',
};

export default function StandPanel({ propertyId, standId, onClose }: StandPanelProps) {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [fieldDataList, setFieldDataList] = useState<FieldData[]>([]);
  const [autoFilling, setAutoFilling] = useState(false);

  const { stands, updateStand, saving } = usePropertyStore();

  const feature = useMemo(
    () => stands.features.find((f) => f.properties.id === standId) as StandFeature | undefined,
    [stands, standId],
  );

  const stand = feature?.properties;

  const { register, handleSubmit, reset, setValue } = useForm<Partial<Stand>>({
    defaultValues: stand ?? {},
  });

  useEffect(() => {
    if (stand) reset(stand);
  }, [stand, reset]);

  // Load field data
  useEffect(() => {
    fieldDataApi.listByStand(standId).then((data: FieldData[]) => {
      setFieldDataList(data);
    }).catch(() => {});
  }, [standId]);

  const onSubmit = async (data: Partial<Stand>) => {
    await updateStand(propertyId, standId, data);
  };

  const handleAutoFill = async () => {
    setAutoFilling(true);
    try {
      const forestData: ForestData = await geodataApi.getForestData(standId);
      const d = forestData.data as Record<string, number>;
      setValue('volumeM3PerHa', d.volumeM3PerHa);
      setValue('basalAreaM2', d.basalAreaM2);
      setValue('meanHeightM', d.meanHeightM);
      setValue('meanDiameterCm', d.meanDiameterCm);
      setValue('pinePct', d.pinePct);
      setValue('sprucePct', d.sprucePct);
      setValue('deciduousPct', d.deciduousPct);
      setValue('contortaPct', d.contortaPct);
    } catch {
      // handle error silently
    } finally {
      setAutoFilling(false);
    }
  };

  if (!stand) {
    return (
      <div className="absolute right-0 top-0 z-30 flex h-full w-[400px] items-center justify-center bg-white shadow-lg">
        <p className="text-gray-500">Avdelning hittades inte</p>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'overview', label: 'Översikt', icon: <TreePine className="h-4 w-4" /> },
    { key: 'forestdata', label: 'Skogsdata', icon: <Mountain className="h-4 w-4" /> },
    { key: 'actions', label: 'Åtgärder', icon: <Clipboard className="h-4 w-4" /> },
    { key: 'economy', label: 'Ekonomi', icon: <DollarSign className="h-4 w-4" /> },
    { key: 'fielddata', label: 'Fältdata', icon: <MapPin className="h-4 w-4" /> },
  ];

  return (
    <div className="absolute right-0 top-0 z-30 flex h-full w-[400px] flex-col border-l border-gray-200 bg-white shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-gray-800">
            Avdelning {stand.standNumber}
          </h2>
          {stand.targetClass && (
            <span className={clsx(
              'rounded-full px-2.5 py-0.5 text-xs font-semibold',
              TARGET_CLASS_COLORS[stand.targetClass],
            )}>
              {stand.targetClass}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              'flex items-center gap-1.5 whitespace-nowrap px-3 py-2.5 text-xs font-medium transition border-b-2',
              activeTab === tab.key
                ? 'border-forest-600 text-forest-700'
                : 'border-transparent text-gray-500 hover:text-gray-700',
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <form onSubmit={handleSubmit(onSubmit)} className="flex-1 overflow-y-auto">
        <div className="p-4">
          {activeTab === 'overview' && (
            <OverviewTab stand={stand} />
          )}
          {activeTab === 'forestdata' && (
            <ForestDataTab
              register={register}
              autoFilling={autoFilling}
              onAutoFill={handleAutoFill}
            />
          )}
          {activeTab === 'actions' && (
            <ActionsTab register={register} stand={stand} />
          )}
          {activeTab === 'economy' && (
            <EconomyTab stand={stand} register={register} />
          )}
          {activeTab === 'fielddata' && (
            <FieldDataTab fieldData={fieldDataList} />
          )}
        </div>

        {/* Footer */}
        {activeTab !== 'overview' && activeTab !== 'fielddata' && (
          <div className="sticky bottom-0 flex gap-2 border-t border-gray-200 bg-white px-4 py-3">
            <button
              type="submit"
              disabled={saving}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-forest-700 px-4 py-2 text-sm font-semibold text-white hover:bg-forest-800 disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {saving ? 'Sparar...' : 'Spara'}
            </button>
            <button
              type="button"
              onClick={() => reset(stand)}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Avbryt
            </button>
          </div>
        )}
      </form>
    </div>
  );
}

/* ───────── Overview Tab ───────── */

function OverviewTab({ stand }: { stand: Partial<Stand> }) {
  const stats = [
    { label: 'Areal', value: formatArea(stand.areaHa ?? 0) },
    { label: 'Volym', value: formatVolume(stand.volumeM3PerHa ?? 0) },
    { label: 'Total volym', value: `${Math.round(stand.totalVolumeM3 ?? 0)} m\u00b3sk` },
    { label: 'Ålder', value: `${stand.ageYears ?? '-'} år` },
    { label: 'Ståndortsindex', value: `SI ${stand.siteIndex ?? '-'}` },
    { label: 'Grundyta', value: `${stand.basalAreaM2 ?? '-'} m\u00b2/ha` },
    { label: 'Medelhöjd', value: `${stand.meanHeightM ?? '-'} m` },
    { label: 'Medeldiameter', value: `${stand.meanDiameterCm ?? '-'} cm` },
  ];

  return (
    <div className="space-y-5">
      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="rounded-lg bg-gray-50 p-3">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className="mt-0.5 text-sm font-semibold text-gray-800">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Species chart */}
      <div>
        <h3 className="mb-2 text-sm font-semibold text-gray-700">Trädslagsfördelning</h3>
        <SpeciesChart
          pine={stand.pinePct ?? 0}
          spruce={stand.sprucePct ?? 0}
          deciduous={stand.deciduousPct ?? 0}
          contorta={stand.contortaPct ?? 0}
        />
      </div>

      {/* Action summary */}
      {stand.proposedAction && stand.proposedAction !== 'ingen' && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-semibold text-amber-800">Föreslagen åtgärd</p>
          <p className="mt-1 text-sm capitalize text-amber-900">
            {stand.proposedAction} ({stand.actionYear})
          </p>
        </div>
      )}
    </div>
  );
}

/* ───────── Forest Data Tab ───────── */

function ForestDataTab({
  register,
  autoFilling,
  onAutoFill,
}: {
  register: ReturnType<typeof useForm<Partial<Stand>>>['register'];
  autoFilling: boolean;
  onAutoFill: () => void;
}) {
  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={onAutoFill}
        disabled={autoFilling}
        className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-forest-300 bg-forest-50 px-4 py-2.5 text-sm font-medium text-forest-700 hover:bg-forest-100 disabled:opacity-50"
      >
        <RefreshCw className={clsx('h-4 w-4', autoFilling && 'animate-spin')} />
        {autoFilling ? 'Hämtar geodata...' : 'Fyll i automatiskt från geodata'}
      </button>

      <FieldGroup label="Grunddata">
        <FormField label="Volym (m\u00b3sk/ha)" name="volumeM3PerHa" type="number" register={register} />
        <FormField label="Grundyta (m\u00b2/ha)" name="basalAreaM2" type="number" register={register} />
        <FormField label="Medelhöjd (m)" name="meanHeightM" type="number" register={register} />
        <FormField label="Medeldiameter (cm)" name="meanDiameterCm" type="number" register={register} />
        <FormField label="Ålder (år)" name="ageYears" type="number" register={register} />
        <FormField label="Ståndortsindex" name="siteIndex" type="number" register={register} />
      </FieldGroup>

      <FieldGroup label="Trädslag (%)">
        <FormField label="Tall" name="pinePct" type="number" register={register} />
        <FormField label="Gran" name="sprucePct" type="number" register={register} />
        <FormField label="Löv" name="deciduousPct" type="number" register={register} />
        <FormField label="Contorta" name="contortaPct" type="number" register={register} />
      </FieldGroup>

      <FieldGroup label="Målklass">
        <SelectField
          label="Målklass"
          name="targetClass"
          register={register}
          options={[
            { value: 'PG', label: 'PG - Produktion med generell hänsyn' },
            { value: 'PF', label: 'PF - Produktion med förstärkt hänsyn' },
            { value: 'NS', label: 'NS - Naturvård, skötselkrävande' },
            { value: 'NO', label: 'NO - Naturvård, orört' },
            { value: 'K', label: 'K - Kombinerat mål' },
          ]}
        />
      </FieldGroup>
    </div>
  );
}

/* ───────── Actions Tab ───────── */

function ActionsTab({ register }: { register: ReturnType<typeof useForm<Partial<Stand>>>['register']; stand?: Partial<Stand> }) {
  return (
    <div className="space-y-4">
      <FieldGroup label="Åtgärdsförslag">
        <SelectField
          label="Åtgärd"
          name="proposedAction"
          register={register}
          options={[
            { value: 'ingen', label: 'Ingen åtgärd' },
            { value: 'slutavverkning', label: 'Slutavverkning' },
            { value: 'gallring', label: 'Gallring' },
            { value: 'rojning', label: 'Röjning' },
            { value: 'foryngring', label: 'Föryngring' },
            { value: 'naturvard', label: 'Naturvårdsåtgärd' },
            { value: 'ovrig', label: 'Övrig' },
          ]}
        />
        <FormField label="Åtgärdsår" name="actionYear" type="number" register={register} />
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-600">Angelägenhet (1-5)</label>
          <input
            type="range"
            min={1}
            max={5}
            className="w-full accent-forest-600"
            {...register('actionUrgency', { valueAsNumber: true })}
          />
          <div className="flex justify-between text-xs text-gray-400">
            <span>Låg</span>
            <span>Hög</span>
          </div>
        </div>
      </FieldGroup>

      <FieldGroup label="Anteckningar">
        <textarea
          rows={4}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
          placeholder="Anteckningar om avdelningen..."
          {...register('notes')}
        />
      </FieldGroup>
    </div>
  );
}

/* ───────── Economy Tab ───────── */

function EconomyTab({ stand, register }: { stand: Partial<Stand>; register: ReturnType<typeof useForm<Partial<Stand>>>['register'] }) {
  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-green-50 p-3">
          <p className="text-xs text-green-600">Bruttovärde</p>
          <p className="text-lg font-bold text-green-800">
            {formatCurrency(stand.grossValueSek ?? 0)}
          </p>
        </div>
        <div className="rounded-lg bg-red-50 p-3">
          <p className="text-xs text-red-600">Avverkningskostnad</p>
          <p className="text-lg font-bold text-red-800">
            {formatCurrency(stand.harvestingCostSek ?? 0)}
          </p>
        </div>
        <div className="col-span-2 rounded-lg bg-forest-50 p-3">
          <p className="text-xs text-forest-600">Nettovärde</p>
          <p className="text-xl font-bold text-forest-800">
            {formatCurrency(stand.netValueSek ?? 0)}
          </p>
        </div>
      </div>

      <FieldGroup label="Volymer">
        <FormField label="Timmervolym (m\u00b3fub)" name="timberVolumeM3" type="number" register={register} />
        <FormField label="Massavedsvolym (m\u00b3fub)" name="pulpwoodVolumeM3" type="number" register={register} />
      </FieldGroup>

      <FieldGroup label="Ekonomiska värden (SEK)">
        <FormField label="Bruttovärde (kr)" name="grossValueSek" type="number" register={register} />
        <FormField label="Avverkningskostnad (kr)" name="harvestingCostSek" type="number" register={register} />
        <FormField label="Nettovärde (kr)" name="netValueSek" type="number" register={register} />
      </FieldGroup>
    </div>
  );
}

/* ───────── Field Data Tab ───────── */

function FieldDataTab({ fieldData }: { fieldData: FieldData[] }) {
  if (fieldData.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <MapPin className="mb-3 h-10 w-10 text-gray-300" />
        <p className="text-sm text-gray-500">Ingen fältdata registrerad</p>
        <p className="mt-1 text-xs text-gray-400">
          Använd fältappen för att samla in data
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {fieldData.map((fd) => (
        <div key={fd.id} className="rounded-lg border border-gray-200 p-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-gray-800">{fd.recordedBy}</p>
            <p className="text-xs text-gray-500">
              {new Date(fd.recordedAt).toLocaleDateString('sv-SE')}
            </p>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-gray-500">Relaskop: </span>
              <span className="font-medium">{fd.relascopeValue}</span>
            </div>
            <div>
              <span className="text-gray-500">Markfukt: </span>
              <span className="font-medium capitalize">{fd.soilMoisture}</span>
            </div>
            <div>
              <span className="text-gray-500">Provträd: </span>
              <span className="font-medium">{fd.sampleTrees?.length ?? 0} st</span>
            </div>
          </div>
          {fd.notes && (
            <p className="mt-2 text-xs text-gray-600">{fd.notes}</p>
          )}
        </div>
      ))}
    </div>
  );
}

/* ───────── Shared form components ───────── */

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-lg border border-gray-200">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
      >
        {label}
        <ChevronDown className={clsx('h-4 w-4 text-gray-400 transition', open && 'rotate-180')} />
      </button>
      {open && <div className="space-y-3 px-3 pb-3">{children}</div>}
    </div>
  );
}

function FormField({
  label,
  name,
  type,
  register,
}: {
  label: string;
  name: string;
  type: string;
  register: ReturnType<typeof useForm<Partial<Stand>>>['register'];
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-600">{label}</label>
      <input
        type={type}
        step={type === 'number' ? 'any' : undefined}
        className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
        {...register(name as keyof Stand, type === 'number' ? { valueAsNumber: true } : undefined)}
      />
    </div>
  );
}

function SelectField({
  label,
  name,
  register,
  options,
}: {
  label: string;
  name: string;
  register: ReturnType<typeof useForm<Partial<Stand>>>['register'];
  options: { value: string; label: string }[];
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-600">{label}</label>
      <select
        className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
        {...register(name as keyof Stand)}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
