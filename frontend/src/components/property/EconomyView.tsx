import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { economicsApi } from '@/services/api';
import { formatArea, formatCurrency, formatNumber } from '@/utils/formatters';
import type { EconomicData } from '@/types';
import {
  Loader2,
  AlertTriangle,
  TreePine,
  Logs,
  Banknote,
  TrendingDown,
  TrendingUp,
  Calculator,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface EconomyViewProps {
  propertyId: string;
}

/* ───────── Action colors for chart ───────── */

const ACTION_CHART_COLORS: Record<string, string> = {
  slutavverkning: '#dc2626',
  gallring: '#f59e0b',
  rojning: '#22c55e',
  foryngring: '#06b6d4',
  ingen: '#9ca3af',
  naturvard: '#10b981',
  ovrig: '#8b5cf6',
};

const ACTION_CHART_LABELS: Record<string, string> = {
  slutavverkning: 'Slutavverkning',
  gallring: 'Gallring',
  rojning: 'Rojning',
  foryngring: 'Foryngring',
  ingen: 'Ingen atgard',
  naturvard: 'Naturvard',
  ovrig: 'Ovrig',
};

/* ───────── Custom tooltip for Recharts ───────── */

function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string }>;
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
      <p className="mb-1 text-sm font-semibold text-gray-800">{label}</p>
      {payload.map((entry, idx) => (
        <p key={idx} className="text-xs text-gray-600">
          <span
            className="mr-1.5 inline-block h-2.5 w-2.5 rounded-sm"
            style={{ backgroundColor: entry.color }}
          />
          {entry.name}: {formatCurrency(entry.value)}
        </p>
      ))}
    </div>
  );
}

/* ───────── Main component ───────── */

export default function EconomyView({ propertyId }: EconomyViewProps) {
  const {
    data: economics,
    isLoading,
    isError,
    error,
  } = useQuery<EconomicData>({
    queryKey: ['propertyEconomics', propertyId],
    queryFn: () => economicsApi.getPropertyEconomics(propertyId),
    enabled: !!propertyId,
  });

  /* ── Prepare chart data: pivot actionsByYear so each action is a separate bar ── */
  const chartData = useMemo((): { data: Record<string, number>[]; actionTypes: string[] } => {
    if (!economics?.actionsByYear) return { data: [], actionTypes: [] };

    // Group by year, each year gets one entry with keys per action type
    const yearMap = new Map<number, Record<string, number>>();
    const actionTypes = new Set<string>();

    for (const entry of economics.actionsByYear) {
      actionTypes.add(entry.action);
      if (!yearMap.has(entry.year)) {
        yearMap.set(entry.year, { year: entry.year });
      }
      const yearEntry = yearMap.get(entry.year)!;
      yearEntry[entry.action] = (yearEntry[entry.action] ?? 0) + entry.totalNetValueSek;
    }

    const sorted = Array.from(yearMap.values()).sort(
      (a, b) => (a.year as number) - (b.year as number),
    );

    return { data: sorted, actionTypes: Array.from(actionTypes) };
  }, [economics?.actionsByYear]);

  /* ── Loading ── */
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-forest-600" />
        <p className="mt-3 text-sm text-gray-500">Laddar ekonomisk sammanstallning...</p>
      </div>
    );
  }

  /* ── Error ── */
  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <AlertTriangle className="h-8 w-8 text-red-500" />
        <p className="mt-3 text-sm text-red-600">
          Kunde inte ladda ekonomisk data.
        </p>
        <p className="mt-1 text-xs text-gray-400">
          {error instanceof Error ? error.message : 'Okant fel'}
        </p>
      </div>
    );
  }

  if (!economics) return null;

  /* ── Summary cards ── */
  const summaryCards = [
    {
      label: 'Timmervolym',
      value: `${formatNumber(economics.totalTimberVolumeM3)} m\u00b3fub`,
      icon: <TreePine className="h-5 w-5" />,
      color: 'bg-forest-50 text-forest-700',
      iconBg: 'bg-forest-100',
    },
    {
      label: 'Massavedsvolym',
      value: `${formatNumber(economics.totalPulpwoodVolumeM3)} m\u00b3fub`,
      icon: <Logs className="h-5 w-5" />,
      color: 'bg-amber-50 text-amber-700',
      iconBg: 'bg-amber-100',
    },
    {
      label: 'Bruttovarde',
      value: formatCurrency(economics.totalGrossValueSek),
      icon: <Banknote className="h-5 w-5" />,
      color: 'bg-green-50 text-green-700',
      iconBg: 'bg-green-100',
    },
    {
      label: 'Avverkningskostnad',
      value: formatCurrency(economics.totalHarvestingCostSek),
      icon: <TrendingDown className="h-5 w-5" />,
      color: 'bg-red-50 text-red-700',
      iconBg: 'bg-red-100',
    },
    {
      label: 'Nettovarde',
      value: formatCurrency(economics.totalNetValueSek),
      icon: <TrendingUp className="h-5 w-5" />,
      color: 'bg-emerald-50 text-emerald-700',
      iconBg: 'bg-emerald-100',
    },
    {
      label: 'NPV 10 ar',
      value: formatCurrency(economics.totalNpv10yr),
      icon: <Calculator className="h-5 w-5" />,
      color: 'bg-sky-50 text-sky-700',
      iconBg: 'bg-sky-100',
    },
  ];

  return (
    <div className="p-6 space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-gray-800">Ekonomisk sammanstallning</h2>
        <p className="mt-1 text-sm text-gray-500">
          Oversikt av virkesvarden, kostnader och nettovarden for alla avdelningar.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        {summaryCards.map((card) => (
          <div key={card.label} className={`rounded-xl ${card.color} p-4`}>
            <div className="flex items-center gap-3">
              <div className={`rounded-lg ${card.iconBg} p-2`}>
                {card.icon}
              </div>
              <div>
                <p className="text-xs font-medium opacity-75">{card.label}</p>
                <p className="text-lg font-bold">{card.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Per-stand economics table */}
      <div>
        <h3 className="mb-3 text-lg font-semibold text-gray-800">
          Ekonomi per avdelning
        </h3>
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-600">
                  Avd. nr
                </th>
                <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-600">
                  Areal (ha)
                </th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">
                  Timmer (m{'\u00b3'}fub)
                </th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">
                  Massaved (m{'\u00b3'}fub)
                </th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">
                  Brutto (kr)
                </th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">
                  Kostnad (kr)
                </th>
                <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">
                  Netto (kr)
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {economics.standEconomics
                .slice()
                .sort((a, b) => a.standNumber - b.standNumber)
                .map((se) => (
                  <tr
                    key={se.standId}
                    className="transition hover:bg-forest-50"
                  >
                    <td className="px-3 py-2 font-semibold text-gray-800">
                      {se.standNumber}
                    </td>
                    <td className="px-3 py-2 text-gray-700">
                      {formatArea(se.areaHa)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-700">
                      {formatNumber(se.timberVolumeM3)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-700">
                      {formatNumber(se.pulpwoodVolumeM3)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-700">
                      {formatCurrency(se.grossValueSek)}
                    </td>
                    <td className="px-3 py-2 text-right text-red-600">
                      {formatCurrency(se.harvestingCostSek)}
                    </td>
                    <td className="px-3 py-2 text-right font-medium text-gray-800">
                      {formatCurrency(se.netValueSek)}
                    </td>
                  </tr>
                ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold">
                <td className="px-3 py-2 text-gray-800">Totalt</td>
                <td className="px-3 py-2">
                  {formatArea(
                    economics.standEconomics.reduce((s, se) => s + se.areaHa, 0),
                  )}
                </td>
                <td className="px-3 py-2 text-right">
                  {formatNumber(economics.totalTimberVolumeM3)}
                </td>
                <td className="px-3 py-2 text-right">
                  {formatNumber(economics.totalPulpwoodVolumeM3)}
                </td>
                <td className="px-3 py-2 text-right">
                  {formatCurrency(economics.totalGrossValueSek)}
                </td>
                <td className="px-3 py-2 text-right text-red-600">
                  {formatCurrency(economics.totalHarvestingCostSek)}
                </td>
                <td className="px-3 py-2 text-right">
                  {formatCurrency(economics.totalNetValueSek)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* Actions by year chart */}
      {chartData && chartData.data.length > 0 && (
        <div>
          <h3 className="mb-3 text-lg font-semibold text-gray-800">
            Atgarder per ar
          </h3>
          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <ResponsiveContainer width="100%" height={350}>
              <BarChart
                data={chartData.data}
                margin={{ top: 10, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="year"
                  tick={{ fontSize: 12 }}
                  stroke="#6b7280"
                />
                <YAxis
                  tick={{ fontSize: 12 }}
                  stroke="#6b7280"
                  tickFormatter={(v: number) =>
                    v >= 1000000
                      ? `${(v / 1000000).toFixed(1)} mkr`
                      : v >= 1000
                        ? `${(v / 1000).toFixed(0)} tkr`
                        : `${v}`
                  }
                />
                <Tooltip content={<ChartTooltip />} />
                <Legend
                  formatter={(value: string) =>
                    ACTION_CHART_LABELS[value] ?? value
                  }
                />
                {chartData.actionTypes.map((action) => (
                  <Bar
                    key={action}
                    dataKey={action}
                    name={action}
                    stackId="actions"
                    fill={ACTION_CHART_COLORS[action] ?? '#6b7280'}
                    radius={[2, 2, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
