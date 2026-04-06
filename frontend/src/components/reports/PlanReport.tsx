import { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { plansApi, propertiesApi, standsApi } from '@/services/api';
import PlanSummary from './PlanSummary';
import type { StandFeature, TargetClass } from '@/types';
import { formatCurrency } from '@/utils/formatters';
import {
  FileText,
  Share2,
  Download,
  CheckCircle2,
  Shield,
  Copy,
  Loader2,
} from 'lucide-react';
import clsx from 'clsx';

const TARGET_CLASS_COLORS: Record<TargetClass, string> = {
  PG: '#22c55e',
  PF: '#3b82f6',
  NS: '#eab308',
  NO: '#f97316',
  K: '#a855f7',
};

/**
 * Format an ISO date string (e.g. "2026-01-01") to just the year,
 * or return '-' if null/undefined.
 */
function formatPlanYear(isoDate: string | null | undefined): string {
  if (!isoDate) return '-';
  const d = new Date(isoDate);
  return isNaN(d.getTime()) ? '-' : String(d.getFullYear());
}

export default function PlanReport() {
  const { id } = useParams<{ id: string }>();
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: plan, isLoading: planLoading } = useQuery({
    queryKey: ['plan', id],
    queryFn: () => plansApi.get(id!),
    enabled: !!id,
  });

  const { data: property } = useQuery({
    queryKey: ['property', plan?.propertyId],
    queryFn: () => propertiesApi.get(plan!.propertyId),
    enabled: !!plan?.propertyId,
  });

  const { data: standsCollection } = useQuery({
    queryKey: ['stands', plan?.propertyId],
    queryFn: () => standsApi.listByProperty(plan!.propertyId),
    enabled: !!plan?.propertyId,
  });

  const features = (standsCollection?.features ?? []) as StandFeature[];

  /* -- Chart data -- */

  // Age distribution histogram
  const ageDistribution = useMemo(() => {
    const bins: Record<string, number> = {};
    const binSize = 20;
    features.forEach((f) => {
      const age = f.properties.ageYears ?? 0;
      const area = f.properties.areaHa ?? 0;
      const binStart = Math.floor(age / binSize) * binSize;
      const label = `${binStart}-${binStart + binSize}`;
      bins[label] = (bins[label] ?? 0) + area;
    });
    return Object.entries(bins)
      .map(([label, area]) => ({ ageClass: label, area: Math.round(area * 10) / 10 }))
      .sort((a, b) => {
        const aNum = parseInt(a.ageClass);
        const bNum = parseInt(b.ageClass);
        return aNum - bNum;
      });
  }, [features]);

  // Volume by species
  const volumeBySpecies = useMemo(() => {
    let pine = 0, spruce = 0, decid = 0, contorta = 0;
    features.forEach((f) => {
      const p = f.properties;
      const tv = p.totalVolumeM3 ?? 0;
      pine += tv * ((p.pinePct ?? 0) / 100);
      spruce += tv * ((p.sprucePct ?? 0) / 100);
      decid += tv * ((p.deciduousPct ?? 0) / 100);
      contorta += tv * ((p.contortaPct ?? 0) / 100);
    });
    return [
      { species: 'Tall', volume: Math.round(pine), color: '#d97706' },
      { species: 'Gran', volume: Math.round(spruce), color: '#15803d' },
      { species: 'Lov', volume: Math.round(decid), color: '#84cc16' },
      { species: 'Contorta', volume: Math.round(contorta), color: '#0d9488' },
    ].filter((d) => d.volume > 0);
  }, [features]);

  // Target class distribution
  const targetClassDist = useMemo(() => {
    const counts: Partial<Record<TargetClass, number>> = {};
    features.forEach((f) => {
      const tc = f.properties.targetClass;
      if (tc) {
        const area = f.properties.areaHa ?? 0;
        counts[tc] = (counts[tc] ?? 0) + area;
      }
    });
    return (Object.entries(counts) as [TargetClass, number][]).map(([tc, area]) => ({
      name: tc,
      area: Math.round(area * 10) / 10,
      color: TARGET_CLASS_COLORS[tc],
    }));
  }, [features]);

  // Action timeline
  const actionTimeline = useMemo(() => {
    const byYear: Record<number, { year: number; count: number; revenue: number }> = {};
    features.forEach((f) => {
      const p = f.properties;
      if (p.proposedAction && p.proposedAction !== 'ingen' && p.actionYear) {
        if (!byYear[p.actionYear]) {
          byYear[p.actionYear] = { year: p.actionYear, count: 0, revenue: 0 };
        }
        byYear[p.actionYear].count += 1;
        byYear[p.actionYear].revenue += p.netValueSek ?? 0;
      }
    });
    return Object.values(byYear).sort((a, b) => a.year - b.year);
  }, [features]);

  const handleGeneratePdf = async () => {
    if (!id) return;
    try {
      const blob = await plansApi.getPdf(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `skogsbruksplan_${property?.name ?? id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // handle error
    }
  };

  const handleShare = async () => {
    if (!plan?.shareToken) return;
    const url = `${window.location.origin}/shared/${plan.shareToken}`;
    setShareUrl(url);
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  if (planLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-forest-600" />
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-gray-500">Skogsbruksplanen hittades inte</p>
      </div>
    );
  }

  const showFsc = plan.certification === 'FSC' || plan.certification === 'both';
  const showPefc = plan.certification === 'PEFC' || plan.certification === 'both';

  return (
    <div className="mx-auto max-w-7xl px-6 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Skogsbruksplan</h1>
          <p className="mt-1 text-sm text-gray-500">
            {property?.name} &middot; {plan.propertyDesignation ?? property?.propertyDesignation} &middot;
            Planperiod {formatPlanYear(plan.validFrom)}--{formatPlanYear(plan.validTo)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleGeneratePdf}
            className="flex items-center gap-2 rounded-lg bg-forest-700 px-4 py-2 text-sm font-medium text-white hover:bg-forest-800"
          >
            <Download className="h-4 w-4" />
            Generera PDF
          </button>
          <button
            onClick={handleShare}
            className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            {copied ? <CheckCircle2 className="h-4 w-4 text-green-600" /> : <Share2 className="h-4 w-4" />}
            {copied ? 'Kopierad!' : 'Dela plan'}
          </button>
        </div>
      </div>

      {/* Certification badges */}
      <div className="flex gap-3">
        {showFsc && (
          <div className="flex items-center gap-1.5 rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800">
            <Shield className="h-3.5 w-3.5" />
            FSC-certifierad
          </div>
        )}
        {showPefc && (
          <div className="flex items-center gap-1.5 rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-800">
            <Shield className="h-3.5 w-3.5" />
            PEFC-certifierad
          </div>
        )}
        <div className={clsx(
          'rounded-full px-3 py-1 text-xs font-semibold',
          plan.status === 'published' ? 'bg-green-100 text-green-800' :
          plan.status === 'draft' ? 'bg-yellow-100 text-yellow-800' :
          'bg-gray-100 text-gray-800',
        )}>
          {plan.status === 'published' ? 'Publicerad' : plan.status === 'draft' ? 'Utkast' : 'Arkiverad'}
        </div>
      </div>

      {/* Share URL */}
      {shareUrl && (
        <div className="flex items-center gap-2 rounded-lg bg-blue-50 p-3">
          <FileText className="h-4 w-4 text-blue-600" />
          <span className="flex-1 text-sm text-blue-800 truncate">{shareUrl}</span>
          <button
            onClick={() => navigator.clipboard.writeText(shareUrl)}
            className="rounded p-1 text-blue-600 hover:bg-blue-100"
          >
            <Copy className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Summary cards */}
      <PlanSummary
        plan={plan}
        stands={features}
        actionsNext5Years={actionTimeline.reduce((s, a) => s + a.count, 0)}
      />

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Age distribution */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-gray-700">Aldersklassfordelning (ha)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={ageDistribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="ageClass" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(v: number) => [`${v} ha`, 'Areal']}
                contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '12px' }}
              />
              <Bar dataKey="area" fill="#22c55e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Volume by species */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-gray-700">Volym per tradslag (m\u00b3sk)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={volumeBySpecies}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="species" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(v: number) => [`${v.toLocaleString('sv-SE')} m\u00b3sk`, 'Volym']}
                contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '12px' }}
              />
              <Bar dataKey="volume" radius={[4, 4, 0, 0]}>
                {volumeBySpecies.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Target class distribution */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-gray-700">Malklassfordelning (ha)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={targetClassDist}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={90}
                paddingAngle={3}
                dataKey="area"
                label={({ name, area }) => `${name}: ${area} ha`}
                labelLine={false}
              >
                {targetClassDist.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(v: number) => [`${v} ha`, 'Areal']}
                contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '12px' }}
              />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '12px' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Action timeline */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-gray-700">Atgardstidslinje</h3>
          {actionTimeline.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={actionTimeline}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(v: number, name: string) => [
                    name === 'count' ? `${v} st` : formatCurrency(v),
                    name === 'count' ? 'Atgarder' : 'Nettointakt',
                  ]}
                  contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '12px' }}
                />
                <Bar yAxisId="left" dataKey="count" fill="#f59e0b" radius={[4, 4, 0, 0]} name="count" />
                <Bar yAxisId="right" dataKey="revenue" fill="#22c55e" radius={[4, 4, 0, 0]} name="revenue" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[250px] items-center justify-center text-sm text-gray-400">
              Inga planerade atgarder
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
