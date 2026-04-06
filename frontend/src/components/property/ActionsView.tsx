import { Fragment, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { economicsApi } from '@/services/api';
import { formatArea, formatCurrency, formatNumber } from '@/utils/formatters';
import type { ActionProposal, ActionType } from '@/types';
import {
  Loader2,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Star,
  TreePine,
  Axe,
  Scissors,
  Sprout,
  Minus,
} from 'lucide-react';
import clsx from 'clsx';

interface ActionsViewProps {
  propertyId: string;
}

/* ───────── Action color mapping ───────── */

const ACTION_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  slutavverkning: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  gallring: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  rojning: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  foryngring: { bg: 'bg-cyan-50', text: 'text-cyan-700', border: 'border-cyan-200' },
  ingen: { bg: 'bg-gray-50', text: 'text-gray-500', border: 'border-gray-200' },
};

const ACTION_LABELS: Record<string, string> = {
  slutavverkning: 'Slutavverkning',
  gallring: 'Gallring',
  rojning: 'Rojning',
  foryngring: 'Foryngring',
  ingen: 'Ingen atgard',
  naturvard: 'Naturvard',
  ovrig: 'Ovrig',
};

const ACTION_ICONS: Record<string, React.ReactNode> = {
  slutavverkning: <Axe className="h-4 w-4" />,
  gallring: <Scissors className="h-4 w-4" />,
  rojning: <TreePine className="h-4 w-4" />,
  foryngring: <Sprout className="h-4 w-4" />,
  ingen: <Minus className="h-4 w-4" />,
};

function getActionStyle(action: ActionType | string | null) {
  if (!action) return ACTION_STYLES.ingen;
  return ACTION_STYLES[action] ?? ACTION_STYLES.ingen;
}

function getActionLabel(action: ActionType | string | null): string {
  if (!action) return 'Ingen atgard';
  return ACTION_LABELS[action] ?? action;
}

/* ───────── Urgency stars ───────── */

function UrgencyStars({ urgency }: { urgency: number | null }) {
  const level = urgency ?? 0;
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          className={clsx(
            'h-3.5 w-3.5',
            i <= level ? 'fill-amber-400 text-amber-400' : 'text-gray-300',
          )}
        />
      ))}
    </div>
  );
}

/* ───────── Main component ───────── */

export default function ActionsView({ propertyId }: ActionsViewProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const {
    data: proposals,
    isLoading,
    isError,
    error,
  } = useQuery<ActionProposal[]>({
    queryKey: ['actionProposals', propertyId],
    queryFn: () => economicsApi.getActionProposals(propertyId),
    enabled: !!propertyId,
  });

  const toggleRow = (standId: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(standId)) {
        next.delete(standId);
      } else {
        next.add(standId);
      }
      return next;
    });
  };

  /* ── Loading ── */
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-forest-600" />
        <p className="mt-3 text-sm text-gray-500">Laddar atgardsforslag...</p>
      </div>
    );
  }

  /* ── Error ── */
  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <AlertTriangle className="h-8 w-8 text-red-500" />
        <p className="mt-3 text-sm text-red-600">
          Kunde inte ladda atgardsforslag.
        </p>
        <p className="mt-1 text-xs text-gray-400">
          {error instanceof Error ? error.message : 'Okant fel'}
        </p>
      </div>
    );
  }

  if (!proposals) return null;

  /* ── Summary ── */
  const withActions = proposals.filter(
    (p) => p.proposedAction && p.proposedAction !== 'ingen',
  );
  const totalStands = proposals.length;
  const standsWithActions = withActions.length;

  /* ── Sort by urgency descending, then stand number ── */
  const sorted = [...proposals].sort((a, b) => {
    const urgA = a.actionUrgency ?? 0;
    const urgB = b.actionUrgency ?? 0;
    if (urgB !== urgA) return urgB - urgA;
    return a.standNumber - b.standNumber;
  });

  return (
    <div className="p-6">
      {/* Summary banner */}
      <div className="mb-6 rounded-xl bg-forest-50 border border-forest-200 p-4">
        <h2 className="text-lg font-bold text-forest-900">
          Atgardsforslag
        </h2>
        <p className="mt-1 text-sm text-forest-700">
          {standsWithActions} avdelningar med foreslagna atgarder av totalt{' '}
          {totalStands}
        </p>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="w-10 px-3 py-2.5" />
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-600">
                Avd. nr
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-600">
                Areal (ha)
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-600">
                Atgard
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-600">
                Bradska
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-600">
                Atgardsar
              </th>
              <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">
                Timmervolym
              </th>
              <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">
                Nettovarde
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sorted.map((proposal) => {
              const style = getActionStyle(proposal.proposedAction);
              const isExpanded = expandedRows.has(proposal.standId);

              return (
                <Fragment key={proposal.standId}>
                  <tr
                    className={clsx(
                      'cursor-pointer transition hover:bg-gray-50',
                      isExpanded && 'bg-gray-50',
                    )}
                    onClick={() => toggleRow(proposal.standId)}
                  >
                    {/* Expand icon */}
                    <td className="px-3 py-2 text-center text-gray-400">
                      {proposal.reasoning ? (
                        isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )
                      ) : null}
                    </td>

                    {/* Stand number */}
                    <td className="px-3 py-2 font-semibold text-gray-800">
                      {proposal.standNumber}
                    </td>

                    {/* Area */}
                    <td className="px-3 py-2 text-gray-700">
                      {formatArea(proposal.areaHa)}
                    </td>

                    {/* Action badge */}
                    <td className="px-3 py-2">
                      <span
                        className={clsx(
                          'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold',
                          style.bg,
                          style.text,
                          style.border,
                        )}
                      >
                        {ACTION_ICONS[proposal.proposedAction ?? 'ingen']}
                        {getActionLabel(proposal.proposedAction)}
                      </span>
                    </td>

                    {/* Urgency */}
                    <td className="px-3 py-2">
                      <UrgencyStars urgency={proposal.actionUrgency} />
                    </td>

                    {/* Action year */}
                    <td className="px-3 py-2 text-gray-700">
                      {proposal.actionYear ?? '-'}
                    </td>

                    {/* Timber volume */}
                    <td className="px-3 py-2 text-right text-gray-700">
                      {proposal.timberVolumeM3 != null
                        ? `${formatNumber(proposal.timberVolumeM3)} m\u00b3fub`
                        : '-'}
                    </td>

                    {/* Net value */}
                    <td className="px-3 py-2 text-right font-medium text-gray-800">
                      {formatCurrency(proposal.netValueSek)}
                    </td>
                  </tr>

                  {/* Expanded reasoning row */}
                  {isExpanded && proposal.reasoning && (
                    <tr className="bg-gray-50">
                      <td />
                      <td colSpan={7} className="px-3 py-3">
                        <div className="rounded-lg bg-white border border-gray-200 p-3">
                          <p className="text-xs font-semibold text-gray-500 uppercase mb-1">
                            Motivering
                          </p>
                          <p className="text-sm text-gray-700 leading-relaxed">
                            {proposal.reasoning}
                          </p>
                          {proposal.pulpwoodVolumeM3 != null && (
                            <p className="mt-2 text-xs text-gray-500">
                              Massavedsvolym:{' '}
                              {formatNumber(proposal.pulpwoodVolumeM3)} m{'\u00b3'}fub
                            </p>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>

          {/* Summary footer */}
          <tfoot>
            <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold">
              <td className="px-3 py-2" />
              <td className="px-3 py-2 text-gray-800">Totalt</td>
              <td className="px-3 py-2">
                {formatArea(
                  proposals.reduce((sum, p) => sum + (p.areaHa ?? 0), 0),
                )}
              </td>
              <td className="px-3 py-2 text-xs text-gray-500">
                {standsWithActions} atgarder
              </td>
              <td className="px-3 py-2" />
              <td className="px-3 py-2" />
              <td className="px-3 py-2 text-right">
                {formatNumber(
                  proposals.reduce(
                    (sum, p) => sum + (p.timberVolumeM3 ?? 0),
                    0,
                  ),
                )}{' '}
                m{'\u00b3'}fub
              </td>
              <td className="px-3 py-2 text-right">
                {formatCurrency(
                  proposals.reduce(
                    (sum, p) => sum + (p.netValueSek ?? 0),
                    0,
                  ),
                )}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
