import { useMemo } from 'react';
import { TreePine, Mountain, Coins, Activity, Calendar, TrendingUp, BarChart3, Layers } from 'lucide-react';
import { formatArea, formatCurrency } from '@/utils/formatters';
import type { ForestPlan, StandFeature } from '@/types';

interface PlanSummaryProps {
  plan: ForestPlan;
  stands?: StandFeature[];
  actionsNext5Years?: number;
}

export default function PlanSummary({ plan, stands = [], actionsNext5Years = 0 }: PlanSummaryProps) {
  const derived = useMemo(() => {
    let totalArea = 0;
    let totalVolume = 0;
    let weightedAgeSum = 0;
    let totalNetValue = 0;

    stands.forEach((f) => {
      const p = f.properties;
      const area = p.areaHa ?? 0;
      totalArea += area;
      totalVolume += p.totalVolumeM3 ?? 0;
      weightedAgeSum += (p.ageYears ?? 0) * area;
      totalNetValue += p.netValueSek ?? 0;
    });

    const meanAge = totalArea > 0 ? Math.round(weightedAgeSum / totalArea) : 0;
    const meanVolumePerHa = totalArea > 0 ? Math.round(totalVolume / totalArea) : 0;

    return { totalArea, totalVolume, meanAge, meanVolumePerHa, totalNetValue };
  }, [stands]);

  // Use plan.totalAreaHa if available (from detail response), otherwise derive from stands
  const displayArea = plan.totalAreaHa ?? derived.totalArea;

  const cards = [
    {
      label: 'Total areal',
      value: formatArea(displayArea),
      icon: <Layers className="h-5 w-5" />,
      color: 'bg-forest-50 text-forest-700',
      iconBg: 'bg-forest-100',
    },
    {
      label: 'Antal avdelningar',
      value: `${plan.standCount ?? stands.length} st`,
      icon: <TreePine className="h-5 w-5" />,
      color: 'bg-green-50 text-green-700',
      iconBg: 'bg-green-100',
    },
    {
      label: 'Total volym',
      value: derived.totalVolume > 0
        ? `${Math.round(derived.totalVolume).toLocaleString('sv-SE')} m\u00b3sk`
        : 'N/A',
      icon: <Mountain className="h-5 w-5" />,
      color: 'bg-emerald-50 text-emerald-700',
      iconBg: 'bg-emerald-100',
    },
    {
      label: 'Medelvolym',
      value: derived.meanVolumePerHa > 0
        ? `${derived.meanVolumePerHa} m\u00b3sk/ha`
        : 'N/A',
      icon: <BarChart3 className="h-5 w-5" />,
      color: 'bg-sky-50 text-sky-700',
      iconBg: 'bg-sky-100',
    },
    {
      label: 'Medelalder',
      value: derived.meanAge > 0 ? `${derived.meanAge} ar` : 'N/A',
      icon: <Calendar className="h-5 w-5" />,
      color: 'bg-amber-50 text-amber-700',
      iconBg: 'bg-amber-100',
    },
    {
      label: 'Tillvaxt',
      value: 'N/A',
      icon: <TrendingUp className="h-5 w-5" />,
      color: 'bg-lime-50 text-lime-700',
      iconBg: 'bg-lime-100',
    },
    {
      label: 'Nettovarde',
      value: derived.totalNetValue > 0 ? formatCurrency(derived.totalNetValue) : 'N/A',
      icon: <Coins className="h-5 w-5" />,
      color: 'bg-yellow-50 text-yellow-700',
      iconBg: 'bg-yellow-100',
    },
    {
      label: 'Atgarder (5 ar)',
      value: `${actionsNext5Years} st`,
      icon: <Activity className="h-5 w-5" />,
      color: 'bg-rose-50 text-rose-700',
      iconBg: 'bg-rose-100',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {cards.map((card) => (
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
  );
}
