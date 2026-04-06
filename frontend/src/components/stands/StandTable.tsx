import { useState, useMemo } from 'react';
import { usePropertyStore } from '@/store/propertyStore';
import { useMapStore } from '@/store/mapStore';
import { formatArea, formatVolume, formatCurrency, formatSpecies } from '@/utils/formatters';
import type { StandFeature, TargetClass } from '@/types';
import { ArrowUpDown, Download, Search } from 'lucide-react';
import clsx from 'clsx';

interface StandTableProps {
  propertyId: string;
}

type SortKey =
  | 'standNumber'
  | 'areaHa'
  | 'volumeM3PerHa'
  | 'ageYears'
  | 'siteIndex'
  | 'species'
  | 'targetClass'
  | 'proposedAction'
  | 'grossValueSek';

type SortDir = 'asc' | 'desc';

const TC_BADGE: Record<TargetClass, string> = {
  PG: 'bg-green-100 text-green-800',
  PF: 'bg-blue-100 text-blue-800',
  NS: 'bg-yellow-100 text-yellow-800',
  NO: 'bg-orange-100 text-orange-800',
  K: 'bg-purple-100 text-purple-800',
};

export default function StandTable({ propertyId }: StandTableProps) {
  const stands = usePropertyStore((s) => s.stands);
  const setSelectedStand = useMapStore((s) => s.setSelectedStand);
  const selectedStandId = useMapStore((s) => s.selectedStandId);

  const [sortKey, setSortKey] = useState<SortKey>('standNumber');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [search, setSearch] = useState('');

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const filteredAndSorted = useMemo(() => {
    let items = [...stands.features] as StandFeature[];

    // Filter by search
    if (search) {
      const q = search.toLowerCase();
      items = items.filter(
        (f) =>
          String(f.properties.standNumber).includes(q) ||
          (f.properties.targetClass ?? '').toLowerCase().includes(q) ||
          (f.properties.proposedAction ?? '').toLowerCase().includes(q),
      );
    }

    // Sort
    items.sort((a, b) => {
      const pa = a.properties;
      const pb = b.properties;
      let cmp = 0;
      switch (sortKey) {
        case 'standNumber':
          cmp = pa.standNumber - pb.standNumber;
          break;
        case 'areaHa':
          cmp = (pa.areaHa ?? 0) - (pb.areaHa ?? 0);
          break;
        case 'volumeM3PerHa':
          cmp = (pa.volumeM3PerHa ?? 0) - (pb.volumeM3PerHa ?? 0);
          break;
        case 'ageYears':
          cmp = (pa.ageYears ?? 0) - (pb.ageYears ?? 0);
          break;
        case 'siteIndex':
          cmp = (pa.siteIndex ?? 0) - (pb.siteIndex ?? 0);
          break;
        case 'species':
          cmp = (pa.pinePct ?? 0) - (pb.pinePct ?? 0);
          break;
        case 'targetClass':
          cmp = (pa.targetClass ?? '').localeCompare(pb.targetClass ?? '');
          break;
        case 'proposedAction':
          cmp = (pa.proposedAction ?? '').localeCompare(pb.proposedAction ?? '');
          break;
        case 'grossValueSek':
          cmp = (pa.grossValueSek ?? 0) - (pb.grossValueSek ?? 0);
          break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });

    return items;
  }, [stands.features, sortKey, sortDir, search]);

  // Summary row
  const totals = useMemo(() => {
    const feats = stands.features as StandFeature[];
    const totalArea = feats.reduce((s, f) => s + (f.properties.areaHa ?? 0), 0);
    const totalVolume = feats.reduce((s, f) => s + (f.properties.totalVolumeM3 ?? 0), 0);
    const avgVolPerHa = totalArea > 0 ? totalVolume / totalArea : 0;
    const avgAge =
      feats.length > 0
        ? feats.reduce((s, f) => s + (f.properties.ageYears ?? 0), 0) / feats.length
        : 0;
    const totalValue = feats.reduce(
      (s, f) => s + (f.properties.grossValueSek ?? 0),
      0,
    );
    return { totalArea, totalVolume, avgVolPerHa, avgAge, totalValue, count: feats.length };
  }, [stands.features]);

  const exportCsv = () => {
    const headers = [
      'Nr', 'Areal (ha)', 'Volym (m3sk/ha)', 'Total volym (m3sk)',
      'Ålder', 'SI', 'Tall%', 'Gran%', 'Löv%', 'Målklass', 'Åtgärd', 'Bruttovärde (kr)',
    ];
    const rows = (stands.features as StandFeature[]).map((f) => {
      const p = f.properties;
      return [
        p.standNumber, (p.areaHa ?? 0).toFixed(1), (p.volumeM3PerHa ?? 0).toFixed(0), (p.totalVolumeM3 ?? 0).toFixed(0),
        p.ageYears ?? '', p.siteIndex ?? '', p.pinePct ?? '', p.sprucePct ?? '', p.deciduousPct ?? '',
        p.targetClass ?? '', p.proposedAction ?? '', Math.round(p.grossValueSek ?? 0),
      ].join(';');
    });
    const csv = [headers.join(';'), ...rows].join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `avdelningar_${propertyId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns: { key: SortKey; label: string; className?: string }[] = [
    { key: 'standNumber', label: 'Nr', className: 'w-14' },
    { key: 'areaHa', label: 'Areal' },
    { key: 'volumeM3PerHa', label: 'Vol m\u00b3/ha' },
    { key: 'ageYears', label: 'Ålder' },
    { key: 'siteIndex', label: 'SI' },
    { key: 'species', label: 'Trädslag' },
    { key: 'targetClass', label: 'Målkl.' },
    { key: 'proposedAction', label: 'Åtgärd' },
    { key: 'grossValueSek', label: 'Bruttovärde' },
  ];

  return (
    <div>
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-800">
          Avdelningar ({totals.count} st)
        </h2>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Sök..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="rounded-lg border border-gray-300 py-1.5 pl-9 pr-3 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
            />
          </div>
          <button
            onClick={exportCsv}
            className="flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <Download className="h-4 w-4" />
            CSV
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={clsx(
                    'cursor-pointer px-3 py-2.5 text-left text-xs font-semibold text-gray-600 hover:text-gray-900',
                    col.className,
                  )}
                  onClick={() => toggleSort(col.key)}
                >
                  <div className="flex items-center gap-1">
                    {col.label}
                    <ArrowUpDown className={clsx(
                      'h-3 w-3',
                      sortKey === col.key ? 'text-forest-700' : 'text-gray-400',
                    )} />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filteredAndSorted.map((f) => {
              const p = f.properties;
              return (
                <tr
                  key={p.id}
                  onClick={() => setSelectedStand(p.id)}
                  className={clsx(
                    'cursor-pointer transition hover:bg-forest-50',
                    selectedStandId === p.id && 'bg-forest-100',
                  )}
                >
                  <td className="px-3 py-2 font-semibold text-gray-800">{p.standNumber}</td>
                  <td className="px-3 py-2">{formatArea(p.areaHa ?? 0)}</td>
                  <td className="px-3 py-2">{formatVolume(p.volumeM3PerHa ?? 0)}</td>
                  <td className="px-3 py-2">{p.ageYears ?? '-'} år</td>
                  <td className="px-3 py-2">
                    {p.siteIndex ?? '-'}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {formatSpecies(p.pinePct ?? 0, p.sprucePct ?? 0, p.deciduousPct ?? 0)}
                  </td>
                  <td className="px-3 py-2">
                    {p.targetClass && (
                    <span className={clsx(
                      'rounded-full px-2 py-0.5 text-xs font-semibold',
                      TC_BADGE[p.targetClass],
                    )}>
                      {p.targetClass}
                    </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs capitalize">{p.proposedAction ?? '-'}</td>
                  <td className="px-3 py-2 text-right font-medium">
                    {formatCurrency(p.grossValueSek ?? 0)}
                  </td>
                </tr>
              );
            })}
          </tbody>

          {/* Summary row */}
          <tfoot>
            <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold">
              <td className="px-3 py-2 text-gray-800">Totalt</td>
              <td className="px-3 py-2">{formatArea(totals.totalArea)}</td>
              <td className="px-3 py-2">{formatVolume(totals.avgVolPerHa)}</td>
              <td className="px-3 py-2">{Math.round(totals.avgAge)} år</td>
              <td className="px-3 py-2">-</td>
              <td className="px-3 py-2">-</td>
              <td className="px-3 py-2">-</td>
              <td className="px-3 py-2">-</td>
              <td className="px-3 py-2 text-right">{formatCurrency(totals.totalValue)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
