import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { plansApi } from '@/services/api';
import { formatDate } from '@/utils/formatters';
import type { ForestPlan } from '@/types';
import {
  Loader2,
  AlertTriangle,
  Plus,
  FileText,
  Download,
  Send,
  Eye,
  Calendar,
  Shield,
  ChevronLeft,
} from 'lucide-react';
import clsx from 'clsx';

interface PlanViewProps {
  propertyId: string;
}

/* ───────── Status badge ───────── */

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  draft: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Utkast' },
  published: { bg: 'bg-green-100', text: 'text-green-800', label: 'Publicerad' },
  archived: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'Arkiverad' },
};

/* ───────── Certification label ───────── */

const CERT_LABELS: Record<string, string> = {
  none: 'Ingen',
  PEFC: 'PEFC',
  FSC: 'FSC',
  both: 'PEFC + FSC',
};

/* ───────── Main component ───────── */

export default function PlanView({ propertyId }: PlanViewProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formName, setFormName] = useState(`Skogsbruksplan ${new Date().getFullYear()}`);
  const [formValidFrom, setFormValidFrom] = useState('');
  const [formValidTo, setFormValidTo] = useState('');
  const [formCertification, setFormCertification] = useState<'none' | 'PEFC' | 'FSC' | 'both'>('none');

  /* ── Fetch plans ── */
  const {
    data: plans,
    isLoading,
    isError,
    error,
  } = useQuery<ForestPlan[]>({
    queryKey: ['plans', propertyId],
    queryFn: () => plansApi.list(propertyId),
    enabled: !!propertyId,
  });

  /* ── Create plan mutation ── */
  const createMutation = useMutation({
    mutationFn: (payload: Partial<ForestPlan>) => plansApi.create(payload),
    onSuccess: (newPlan) => {
      queryClient.invalidateQueries({ queryKey: ['plans', propertyId] });
      navigate(`/plans/${newPlan.id}`);
    },
  });

  /* ── Publish plan mutation ── */
  const publishMutation = useMutation({
    mutationFn: (planId: string) => plansApi.publish(planId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans', propertyId] });
    },
  });

  /* ── Download PDF ── */
  const handleDownloadPdf = async (planId: string, planName: string) => {
    try {
      const blob = await plansApi.getPdf(planId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${planName.replace(/\s+/g, '_')}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // PDF download error is handled silently; user sees the button state
    }
  };

  /* ── Create plan handler ── */
  const handleCreatePlan = () => {
    createMutation.mutate({
      propertyId,
      name: formName,
      validFrom: formValidFrom || null,
      validTo: formValidTo || null,
      certification: formCertification,
    });
  };

  /* ── Loading ── */
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-forest-600" />
        <p className="mt-3 text-sm text-gray-500">Laddar skogsbruksplaner...</p>
      </div>
    );
  }

  /* ── Error ── */
  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <AlertTriangle className="h-8 w-8 text-red-500" />
        <p className="mt-3 text-sm text-red-600">
          Kunde inte ladda skogsbruksplaner.
        </p>
        <p className="mt-1 text-xs text-gray-400">
          {error instanceof Error ? error.message : 'Okant fel'}
        </p>
      </div>
    );
  }

  const hasPlan = plans && plans.length > 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800">Skogsbruksplaner</h2>
          <p className="mt-1 text-sm text-gray-500">
            {hasPlan
              ? `${plans.length} plan${plans.length > 1 ? 'er' : ''} for denna fastighet`
              : 'Inga planer skapade annu'}
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="flex items-center gap-2 rounded-lg bg-forest-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-forest-800 transition"
        >
          {showCreateForm ? (
            <>
              <ChevronLeft className="h-4 w-4" />
              Avbryt
            </>
          ) : (
            <>
              <Plus className="h-4 w-4" />
              Skapa ny plan
            </>
          )}
        </button>
      </div>

      {/* Create plan form */}
      {showCreateForm && (
        <div className="rounded-xl border border-forest-200 bg-forest-50 p-6">
          <h3 className="text-lg font-semibold text-forest-900 mb-4">
            Skapa skogsbruksplan
          </h3>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Name */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Plannamn
              </label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
                placeholder="Skogsbruksplan 2026"
              />
            </div>

            {/* Valid from */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <Calendar className="mr-1 inline h-4 w-4" />
                Giltig fran
              </label>
              <input
                type="date"
                value={formValidFrom}
                onChange={(e) => setFormValidFrom(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
              />
            </div>

            {/* Valid to */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <Calendar className="mr-1 inline h-4 w-4" />
                Giltig till
              </label>
              <input
                type="date"
                value={formValidTo}
                onChange={(e) => setFormValidTo(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
              />
            </div>

            {/* Certification */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <Shield className="mr-1 inline h-4 w-4" />
                Certifiering
              </label>
              <select
                value={formCertification}
                onChange={(e) =>
                  setFormCertification(e.target.value as 'none' | 'PEFC' | 'FSC' | 'both')
                }
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
              >
                <option value="none">Ingen certifiering</option>
                <option value="PEFC">PEFC</option>
                <option value="FSC">FSC</option>
                <option value="both">PEFC + FSC</option>
              </select>
            </div>
          </div>

          {/* Submit */}
          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={handleCreatePlan}
              disabled={createMutation.isPending || !formName.trim()}
              className="flex items-center gap-2 rounded-lg bg-forest-700 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-forest-800 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {createMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Skapa plan
            </button>

            {createMutation.isError && (
              <p className="text-sm text-red-600">
                Kunde inte skapa plan:{' '}
                {createMutation.error instanceof Error
                  ? createMutation.error.message
                  : 'Okant fel'}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Existing plans list */}
      {hasPlan && (
        <div className="space-y-4">
          {plans
            .slice()
            .sort(
              (a, b) =>
                new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
            )
            .map((plan) => {
              const statusStyle = STATUS_STYLES[plan.status] ?? STATUS_STYLES.draft;

              return (
                <div
                  key={plan.id}
                  className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md"
                >
                  <div className="flex items-start justify-between">
                    {/* Plan info */}
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <FileText className="h-5 w-5 text-forest-600" />
                        <h3 className="text-lg font-semibold text-gray-800">
                          {plan.name}
                        </h3>
                        <span
                          className={clsx(
                            'rounded-full px-2.5 py-0.5 text-xs font-semibold',
                            statusStyle.bg,
                            statusStyle.text,
                          )}
                        >
                          {statusStyle.label}
                        </span>
                      </div>

                      <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-gray-500">
                        <span>Version {plan.version}</span>

                        {plan.certification && plan.certification !== 'none' && (
                          <span className="flex items-center gap-1">
                            <Shield className="h-3.5 w-3.5" />
                            {CERT_LABELS[plan.certification] ?? plan.certification}
                          </span>
                        )}

                        {plan.validFrom && (
                          <span>
                            Giltig: {formatDate(plan.validFrom)}
                            {plan.validTo ? ` - ${formatDate(plan.validTo)}` : ''}
                          </span>
                        )}

                        {plan.standCount != null && (
                          <span>{plan.standCount} avdelningar</span>
                        )}

                        {plan.totalAreaHa != null && (
                          <span>
                            {plan.totalAreaHa.toLocaleString('sv-SE', {
                              minimumFractionDigits: 1,
                              maximumFractionDigits: 1,
                            })}{' '}
                            ha
                          </span>
                        )}
                      </div>

                      <p className="mt-1 text-xs text-gray-400">
                        Skapad {formatDate(plan.createdAt)} | Uppdaterad{' '}
                        {formatDate(plan.updatedAt)}
                      </p>
                    </div>

                    {/* Action buttons */}
                    <div className="ml-4 flex items-center gap-2">
                      {/* View */}
                      <button
                        onClick={() => navigate(`/plans/${plan.id}`)}
                        className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
                      >
                        <Eye className="h-4 w-4" />
                        Visa
                      </button>

                      {/* Download PDF */}
                      <button
                        onClick={() => handleDownloadPdf(plan.id, plan.name)}
                        className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
                      >
                        <Download className="h-4 w-4" />
                        Ladda ner PDF
                      </button>

                      {/* Publish (only for drafts) */}
                      {plan.status === 'draft' && (
                        <button
                          onClick={() => publishMutation.mutate(plan.id)}
                          disabled={publishMutation.isPending}
                          className="flex items-center gap-1.5 rounded-lg bg-forest-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-forest-800 disabled:opacity-50 transition"
                        >
                          {publishMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Send className="h-4 w-4" />
                          )}
                          Publicera
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
        </div>
      )}

      {/* Empty state (no plans and form not shown) */}
      {!hasPlan && !showCreateForm && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-300 py-16">
          <FileText className="h-12 w-12 text-gray-300" />
          <p className="mt-4 text-lg font-medium text-gray-600">
            Ingen skogsbruksplan annu
          </p>
          <p className="mt-1 text-sm text-gray-400">
            Skapa en plan for att sammanstalla avdelningsdata, atgardsforslag och ekonomi.
          </p>
          <button
            onClick={() => setShowCreateForm(true)}
            className="mt-6 flex items-center gap-2 rounded-lg bg-forest-700 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-forest-800 transition"
          >
            <Plus className="h-4 w-4" />
            Skapa skogsbruksplan
          </button>
        </div>
      )}
    </div>
  );
}
