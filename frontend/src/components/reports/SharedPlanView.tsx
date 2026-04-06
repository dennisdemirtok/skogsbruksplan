import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { plansApi } from '@/services/api';
import PlanSummary from './PlanSummary';
import { TreePine, Loader2, AlertTriangle } from 'lucide-react';

export default function SharedPlanView() {
  const { token } = useParams<{ token: string }>();

  const { data: plan, isLoading, error } = useQuery({
    queryKey: ['shared-plan', token],
    queryFn: () => plansApi.getShared(token!),
    enabled: !!token,
  });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <Loader2 className="h-10 w-10 animate-spin text-forest-600" />
      </div>
    );
  }

  if (error || !plan) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <AlertTriangle className="mx-auto mb-4 h-12 w-12 text-amber-500" />
          <h2 className="text-lg font-semibold text-gray-800">Planen kunde inte hittas</h2>
          <p className="mt-1 text-sm text-gray-500">
            Länken kan ha upphört att gälla eller vara ogiltig.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-forest-700">
            <TreePine className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900">Skogsbruksplan</h1>
            <p className="text-sm text-gray-500">
              {plan.name} &middot; {plan.propertyDesignation ?? ''}
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8 space-y-6">
        {/* Plan info */}
        <div className="rounded-xl bg-white p-6 shadow-sm border border-gray-200">
          <h2 className="text-xl font-bold text-gray-800">{plan.name}</h2>
          <p className="mt-1 text-sm text-gray-500">
            {plan.validFrom && plan.validTo
              ? `Planperiod: ${plan.validFrom}–${plan.validTo}`
              : `Version ${plan.version}`}
            {' '}&middot; Skapad av {plan.createdBy ?? 'okänd'}
          </p>
          <div className="mt-4 flex gap-2">
            {(plan.certification === 'FSC' || plan.certification === 'both') && (
              <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800">
                FSC
              </span>
            )}
            {(plan.certification === 'PEFC' || plan.certification === 'both') && (
              <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-800">
                PEFC
              </span>
            )}
          </div>
        </div>

        {/* Summary */}
        <PlanSummary plan={plan} />

        {/* Note */}
        <div className="rounded-lg bg-forest-50 p-4 text-sm text-forest-800">
          Detta är en delad vy av skogsbruksplanen. Logga in för att se fullständig information
          inklusive karta, avdelningsdata och åtgärdsförslag.
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white py-6 text-center">
        <p className="text-xs text-gray-400">
          Genererad med SkogsplanSaaS &middot; Digital skogsbruksplanering
        </p>
      </footer>
    </div>
  );
}
