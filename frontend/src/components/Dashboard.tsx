import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import maplibregl from 'maplibre-gl';
import { useAuthStore } from '@/store/authStore';
import { usePropertyStore } from '@/store/propertyStore';
import { useQuery } from '@tanstack/react-query';
import { plansApi, economicsApi, weatherApi, satelliteApi } from '@/services/api';
import type { ForestPlan } from '@/types';
import {
  Plus,
  Smartphone,
  MapPin,
  TreePine,
  FileText,
  ArrowRight,
  Loader2,
  AlertTriangle,
  TrendingUp,
  DollarSign,
  BarChart3,
  Shield,
  CloudRain,
  Wind,
  Thermometer,
  Bug,
  CheckCircle2,
  Info,
  AlertOctagon,
  Satellite,
  Eye,
} from 'lucide-react';

/* ── Action name translations ── */
const ACTION_LABELS: Record<string, string> = {
  slutavverkning: 'Slutavverkning',
  gallring: 'Gallring',
  rojning: 'Röjning',
  foryngring: 'Föryngring',
  ingen: 'Ingen åtgärd',
  naturvard: 'Naturvård',
  ovrig: 'Övrigt',
};

const TARGET_CLASS_LABELS: Record<string, string> = {
  PG: 'Produktion',
  PF: 'Förstärkt hänsyn',
  NS: 'Naturvård, skötsel',
  NO: 'Naturvård, orörd',
};

const TARGET_CLASS_COLORS: Record<string, string> = {
  PG: 'bg-green-500',
  PF: 'bg-amber-500',
  NS: 'bg-blue-500',
  NO: 'bg-purple-500',
};


/* ── Types for summary data (matches backend PropertySummaryResponse after camelCase conversion) ── */
interface PropertySummaryApi {
  propertyId: string;
  designation: string;
  totalAreaHa: number;
  productiveForestHa: number;
  standCount: number;
  totalVolumeM3sk: number;
  meanVolumePerHa: number;
  meanAgeYears: number;
  meanSiteIndex: number;
  speciesDistribution: {
    pinePct: number;
    sprucePct: number;
    deciduousPct: number;
    contortaPct: number;
  };
  ageClassDistribution: Array<{ ageClass: string; areaHa: number; standCount: number }>;
  targetClassDistribution: Array<{ targetClass: string; areaHa: number; standCount: number }>;
}

/* Matches backend PropertyAlertsResponse */
interface AlertItemApi {
  severity: string;
  category: string;
  title: string;
  message: string;
  affectedStands: Array<number | null>;
  data: Record<string, unknown>;
  action: string | null;
}

interface PropertyAlertsApi {
  propertyId: string;
  alertCount: number;
  criticalCount: number;
  warningCount: number;
  alerts: AlertItemApi[];
  weatherSource: string;
}

/* Matches backend ForecastResponse (summary only) */
interface ForecastSummaryApi {
  latitude: number;
  longitude: number;
  approvedTime: string | null;
  source: string;
  forecastHours: number;
  summary: {
    maxWindSpeedMs: number;
    maxWindGustMs: number;
    minTemperatureC: number;
    maxTemperatureC: number;
    totalPrecipitationMm: number;
    stormRisk: boolean;
    frostRisk: boolean;
    heavyRainRisk: boolean;
  };
}

/* Matches backend NdviResponse (satellite) */
interface StandNdviApi {
  standNumber: number;
  ndviMean: number | null;
  ndviMedian: number | null;
  healthScore: number | null;
  validPixelCount: number | null;
  classification: Record<string, { count: number; pct: number }> | null;
  error: string | null;
}

interface SatelliteNdviApi {
  propertyId: string;
  sceneDate: string | null;
  sceneId: string | null;
  cloudCover: number | null;
  stands: StandNdviApi[];
  overallNdviMean: number | null;
  overallHealthScore: number | null;
}

/* Matches backend ActionsResponse */
interface ActionsResponseApi {
  propertyId: string;
  totalStands: number;
  standsWithActions: number;
  actions: Array<{
    standId: string;
    standNumber: number;
    areaHa: number;
    action: string;
    urgency: number;
    reasoning: string;
    actionYear: number | null;
    timberVolumeM3: number;
    pulpwoodVolumeM3: number;
    netValueSek: number;
  }>;
}

export default function Dashboard() {
  const user = useAuthStore((s) => s.user);
  const { properties, propertiesLoading, fetchProperties } = usePropertyStore();
  const navigate = useNavigate();
  const [selectedPropertyId, setSelectedPropertyId] = useState<string | null>(null);

  const { data: plans = [] } = useQuery({
    queryKey: ['plans'],
    queryFn: () => plansApi.list(),
  });

  useEffect(() => {
    fetchProperties();
  }, [fetchProperties]);

  // Auto-select first property when loaded
  useEffect(() => {
    if (properties.length > 0 && !selectedPropertyId) {
      setSelectedPropertyId(properties[0].id);
    }
  }, [properties, selectedPropertyId]);

  // Fetch summary data for selected property
  const { data: propertySummary, isLoading: summaryLoading } = useQuery<PropertySummaryApi>({
    queryKey: ['property-summary', selectedPropertyId],
    queryFn: () => economicsApi.getPropertySummary(selectedPropertyId!) as unknown as Promise<PropertySummaryApi>,
    enabled: !!selectedPropertyId,
  });

  // Fetch economics data for selected property
  const { data: economicData } = useQuery({
    queryKey: ['property-economics', selectedPropertyId],
    queryFn: () => economicsApi.getPropertyEconomics(selectedPropertyId!),
    enabled: !!selectedPropertyId,
  });

  // Fetch action proposals for selected property
  const { data: actionsResponse, isLoading: actionsLoading } = useQuery<ActionsResponseApi>({
    queryKey: ['property-actions', selectedPropertyId],
    queryFn: () => economicsApi.getActionProposals(selectedPropertyId!) as Promise<unknown> as Promise<ActionsResponseApi>,
    enabled: !!selectedPropertyId,
  });

  // Fetch smart alerts for selected property
  const { data: alertsData, isLoading: alertsLoading } = useQuery<PropertyAlertsApi>({
    queryKey: ['property-alerts', selectedPropertyId],
    queryFn: () => weatherApi.getAlerts(selectedPropertyId!) as unknown as Promise<PropertyAlertsApi>,
    enabled: !!selectedPropertyId,
    staleTime: 5 * 60 * 1000, // 5 min
  });

  // Fetch weather forecast for selected property
  const { data: forecastData } = useQuery<ForecastSummaryApi>({
    queryKey: ['property-forecast', selectedPropertyId],
    queryFn: () => weatherApi.getForecast(selectedPropertyId!) as unknown as Promise<ForecastSummaryApi>,
    enabled: !!selectedPropertyId,
    staleTime: 15 * 60 * 1000, // 15 min
  });

  // Fetch satellite NDVI data for selected property
  const { data: satelliteData, isLoading: satelliteLoading } = useQuery<SatelliteNdviApi>({
    queryKey: ['property-satellite', selectedPropertyId],
    queryFn: () => satelliteApi.getNdvi(selectedPropertyId!) as unknown as Promise<SatelliteNdviApi>,
    enabled: !!selectedPropertyId,
    staleTime: 30 * 60 * 1000, // 30 min (satellite data changes slowly)
  });

  // Extract action list from response
  const allActions = useMemo(() => actionsResponse?.actions ?? [], [actionsResponse]);

  // Find plans for selected property
  const propertyPlans = useMemo(
    () => plans.filter((p: ForestPlan) => p.propertyId === selectedPropertyId),
    [plans, selectedPropertyId],
  );

  // Compute stand counts from plans
  const totalStandCount = useMemo(() => {
    return plans.reduce((sum: number, p: ForestPlan) => sum + (p.standCount ?? 0), 0);
  }, [plans]);

  // Urgent actions (priority 1-3) that are not "ingen"
  const urgentActions = useMemo(
    () => allActions.filter((a) => a.urgency <= 3 && a.action !== 'ingen'),
    [allActions],
  );

  // Compute derived values for summary display
  const summary = propertySummary;
  const totalStandsArea = useMemo(() => {
    if (!summary) return 0;
    return summary.ageClassDistribution.reduce((s, c) => s + c.areaHa, 0);
  }, [summary]);

  return (
    <div className="mx-auto max-w-7xl px-6 py-6 space-y-8">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Välkommen, {user?.name ?? 'Användare'}
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Här är en överblick av dina skogsfastigheter och planer.
        </p>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <QuickActionCard
          icon={<Plus className="h-6 w-6" />}
          title="Ny fastighet"
          description="Lägg till en ny skogsfastighet"
          onClick={() => navigate('/properties?action=new')}
          color="bg-forest-50 text-forest-700"
        />
        <QuickActionCard
          icon={<Smartphone className="h-6 w-6" />}
          title="Öppna fältapp"
          description="Samla in fältdata med GPS"
          onClick={() => navigate('/field')}
          color="bg-sky-50 text-sky-700"
        />
        <QuickActionCard
          icon={<FileText className="h-6 w-6" />}
          title="Skapa plan"
          description="Starta en ny skogsbruksplan"
          onClick={() => {
            if (properties.length > 0) {
              navigate(`/properties/${properties[0].id}?tab=plan`);
            } else {
              navigate('/properties?action=new');
            }
          }}
          color="bg-amber-50 text-amber-700"
        />
        <QuickActionCard
          icon={<MapPin className="h-6 w-6" />}
          title="Alla fastigheter"
          description={`${properties.length} registrerade fastigheter`}
          onClick={() => navigate('/properties')}
          color="bg-bark-50 text-bark-700"
        />
      </div>

      {/* Top-level stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Fastigheter" value={properties.length} icon={<MapPin className="h-5 w-5" />} />
        <StatCard label="Avdelningar" value={totalStandCount} icon={<TreePine className="h-5 w-5" />} />
        <StatCard label="Planer" value={plans.length} icon={<FileText className="h-5 w-5" />} />
        <StatCard
          label="Brådskande åtgärder"
          value={urgentActions.length}
          icon={<AlertTriangle className="h-5 w-5" />}
          highlight={urgentActions.length > 0}
        />
      </div>

      {/* Property selector for skogsbruksplan data */}
      {properties.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-800">
              Skogsbruksplansdata för fastighet
            </h2>
            <select
              value={selectedPropertyId ?? ''}
              onChange={(e) => setSelectedPropertyId(e.target.value)}
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
            >
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.propertyDesignation || p.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Property-specific skogsbruksplan widgets */}
      {selectedPropertyId && (
        <>
          {/* Smart Alerts & Weather */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Alerts panel */}
            <div className="lg:col-span-2 rounded-xl border border-gray-200 bg-white">
              <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  <h2 className="text-sm font-semibold text-gray-800">Risker & Bevakning</h2>
                </div>
                {alertsData && (
                  <div className="flex items-center gap-2">
                    {alertsData.criticalCount > 0 && (
                      <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">
                        {alertsData.criticalCount} kritiska
                      </span>
                    )}
                    {alertsData.warningCount > 0 && (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-700">
                        {alertsData.warningCount} varningar
                      </span>
                    )}
                  </div>
                )}
              </div>
              <div className="divide-y divide-gray-50 max-h-96 overflow-y-auto">
                {alertsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                    <span className="ml-2 text-sm text-gray-500">Analyserar risker...</span>
                  </div>
                ) : !alertsData || alertsData.alerts.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-8 text-gray-400">
                    <CheckCircle2 className="h-8 w-8 mb-2 text-green-400" />
                    <span className="text-sm">Inga aktiva varningar</span>
                  </div>
                ) : (
                  alertsData.alerts.map((alert, idx) => (
                    <AlertCard key={`${alert.category}-${idx}`} alert={alert} />
                  ))
                )}
              </div>
            </div>

            {/* Weather widget */}
            <div className="rounded-xl border border-gray-200 bg-white">
              <div className="flex items-center gap-2 border-b border-gray-100 px-5 py-4">
                <CloudRain className="h-4 w-4 text-sky-600" />
                <h2 className="text-sm font-semibold text-gray-800">Väderprognos (48h)</h2>
              </div>
              <div className="p-5">
                {forecastData?.summary ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <WeatherStat
                        icon={<Thermometer className="h-4 w-4 text-red-500" />}
                        label="Temperatur"
                        value={`${forecastData.summary.minTemperatureC.toFixed(0)}° – ${forecastData.summary.maxTemperatureC.toFixed(0)}°`}
                      />
                      <WeatherStat
                        icon={<Wind className="h-4 w-4 text-blue-500" />}
                        label="Vind (byar)"
                        value={`${forecastData.summary.maxWindGustMs.toFixed(0)} m/s`}
                        warning={forecastData.summary.stormRisk}
                      />
                      <WeatherStat
                        icon={<CloudRain className="h-4 w-4 text-sky-500" />}
                        label="Nederbörd"
                        value={`${forecastData.summary.totalPrecipitationMm.toFixed(0)} mm`}
                        warning={forecastData.summary.heavyRainRisk}
                      />
                      <WeatherStat
                        icon={<Wind className="h-4 w-4 text-gray-500" />}
                        label="Max vind"
                        value={`${forecastData.summary.maxWindSpeedMs.toFixed(0)} m/s`}
                      />
                    </div>

                    {/* Risk indicators */}
                    <div className="space-y-2">
                      {forecastData.summary.stormRisk && (
                        <div className="flex items-center gap-2 rounded-lg bg-red-50 p-2.5 text-sm text-red-800">
                          <AlertOctagon className="h-4 w-4 flex-shrink-0" />
                          <span className="font-medium">Stormrisk – vindbyar över 21 m/s</span>
                        </div>
                      )}
                      {forecastData.summary.heavyRainRisk && (
                        <div className="flex items-center gap-2 rounded-lg bg-sky-50 p-2.5 text-sm text-sky-800">
                          <CloudRain className="h-4 w-4 flex-shrink-0" />
                          <span className="font-medium">Kraftig nederbörd väntas</span>
                        </div>
                      )}
                      {forecastData.summary.frostRisk && (
                        <div className="flex items-center gap-2 rounded-lg bg-blue-50 p-2.5 text-sm text-blue-800">
                          <Thermometer className="h-4 w-4 flex-shrink-0" />
                          <span className="font-medium">Risk för kraftig frost</span>
                        </div>
                      )}
                      {!forecastData.summary.stormRisk &&
                        !forecastData.summary.heavyRainRisk &&
                        !forecastData.summary.frostRisk && (
                          <div className="flex items-center gap-2 rounded-lg bg-green-50 p-2.5 text-sm text-green-800">
                            <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                            <span className="font-medium">Inga väderrisker</span>
                          </div>
                        )}
                    </div>

                    <p className="text-xs text-gray-400">
                      Källa: SMHI{forecastData.approvedTime ? ` · Uppdaterad: ${new Date(forecastData.approvedTime).toLocaleString('sv-SE', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}` : ''}
                    </p>
                  </div>
                ) : (
                  <div className="flex items-center justify-center py-8 text-gray-400">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="ml-2 text-sm">Hämtar väderdata...</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Satellite Health Monitor */}
          <div className="rounded-xl border border-gray-200 bg-white">
            <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
              <div className="flex items-center gap-2">
                <Satellite className="h-4 w-4 text-indigo-600" />
                <h2 className="text-sm font-semibold text-gray-800">Satellitövervakning (Sentinel-2)</h2>
              </div>
              {satelliteData?.sceneDate && (
                <span className="text-xs text-gray-400">
                  Senaste bild: {new Date(satelliteData.sceneDate).toLocaleDateString('sv-SE')}
                  {satelliteData.cloudCover != null && ` · ${satelliteData.cloudCover.toFixed(0)}% moln`}
                </span>
              )}
            </div>
            <div className="p-5">
              {satelliteLoading ? (
                <div className="flex items-center justify-center py-6 text-gray-400">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span className="ml-2 text-sm">Analyserar satellitbilder...</span>
                </div>
              ) : satelliteData?.stands && satelliteData.stands.length > 0 ? (
                <div className="space-y-4">
                  {/* Overall health score */}
                  <div className="flex items-center gap-4">
                    <div className="relative h-20 w-20 flex-shrink-0">
                      <svg className="h-20 w-20 -rotate-90" viewBox="0 0 36 36">
                        <path
                          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                          fill="none"
                          stroke="#e5e7eb"
                          strokeWidth="3"
                        />
                        <path
                          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                          fill="none"
                          stroke={
                            (satelliteData.overallHealthScore ?? 0) >= 70
                              ? '#22c55e'
                              : (satelliteData.overallHealthScore ?? 0) >= 40
                                ? '#f59e0b'
                                : '#ef4444'
                          }
                          strokeWidth="3"
                          strokeDasharray={`${satelliteData.overallHealthScore ?? 0}, 100`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-lg font-bold text-gray-900">
                          {satelliteData.overallHealthScore ?? '–'}
                        </span>
                      </div>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">
                        Skogshälsa: {
                          (satelliteData.overallHealthScore ?? 0) >= 70
                            ? 'God'
                            : (satelliteData.overallHealthScore ?? 0) >= 40
                              ? 'Måttlig'
                              : 'Svag'
                        }
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        Medel-NDVI: {satelliteData.overallNdviMean?.toFixed(3) ?? '–'}
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {satelliteData.stands.length} avdelningar analyserade
                      </p>
                    </div>
                  </div>

                  {/* Per-stand NDVI bars */}
                  <div className="space-y-1.5">
                    <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">NDVI per avdelning</p>
                    {satelliteData.stands
                      .filter((s) => s.ndviMean != null)
                      .sort((a, b) => (a.healthScore ?? 0) - (b.healthScore ?? 0))
                      .map((stand) => (
                        <div key={stand.standNumber} className="flex items-center gap-2">
                          <span className="w-8 text-right text-xs font-medium text-gray-600">
                            {stand.standNumber}
                          </span>
                          <div className="flex-1 h-4 rounded-full bg-gray-100 overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all ${
                                (stand.healthScore ?? 0) >= 70
                                  ? 'bg-green-500'
                                  : (stand.healthScore ?? 0) >= 40
                                    ? 'bg-amber-500'
                                    : 'bg-red-500'
                              }`}
                              style={{ width: `${Math.min(stand.healthScore ?? 0, 100)}%` }}
                            />
                          </div>
                          <span className="w-16 text-right text-xs text-gray-500">
                            {stand.ndviMean?.toFixed(2)}
                            <span className="text-gray-400 ml-1">({stand.healthScore})</span>
                          </span>
                        </div>
                      ))}
                  </div>

                  <p className="text-xs text-gray-400">
                    Källa: ESA Sentinel-2 (10m upplösning) · NDVI = vegetationsindex (0–1, högre = friskare)
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-6 text-gray-400">
                  <Eye className="h-8 w-8 mb-2" />
                  <span className="text-sm">
                    {satelliteData?.stands?.length === 0
                      ? 'Rita avdelningsgränser för att aktivera satellitanalys'
                      : 'Inga satellitbilder tillgängliga'}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Key forest metrics */}
          {summary && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              <MetricCard
                label="Total areal"
                value={`${(summary.totalAreaHa ?? 0).toFixed(1)}`}
                unit="ha"
                icon={<MapPin className="h-4 w-4" />}
              />
              <MetricCard
                label="Produktiv skog"
                value={`${(summary.productiveForestHa ?? 0).toFixed(1)}`}
                unit="ha"
                icon={<TreePine className="h-4 w-4" />}
              />
              <MetricCard
                label="Virkesförråd"
                value={`${Math.round(summary.totalVolumeM3sk ?? 0)}`}
                unit="m³sk"
                icon={<BarChart3 className="h-4 w-4" />}
              />
              <MetricCard
                label="Medelvolym"
                value={`${Math.round(summary.meanVolumePerHa ?? 0)}`}
                unit="m³sk/ha"
                icon={<TrendingUp className="h-4 w-4" />}
              />
              <MetricCard
                label="Avdelningar"
                value={`${summary.standCount ?? 0}`}
                unit="st"
                icon={<TreePine className="h-4 w-4" />}
              />
              <MetricCard
                label="Nettovärde"
                value={economicData ? formatSEK(economicData.totalNetValueSek) : '-'}
                unit="kr"
                icon={<DollarSign className="h-4 w-4" />}
              />
            </div>
          )}
          {summaryLoading && (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              <span className="ml-2 text-sm text-gray-500">Laddar skogsdata...</span>
            </div>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Species distribution */}
            {summary?.speciesDistribution && (
              <div className="rounded-xl border border-gray-200 bg-white">
                <div className="border-b border-gray-100 px-5 py-4">
                  <h2 className="text-sm font-semibold text-gray-800">Trädslagsfördelning</h2>
                </div>
                <div className="p-5">
                  <SpeciesBar distribution={{
                    pine: summary.speciesDistribution.pinePct,
                    spruce: summary.speciesDistribution.sprucePct,
                    deciduous: summary.speciesDistribution.deciduousPct,
                    contorta: summary.speciesDistribution.contortaPct,
                  }} />
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <SpeciesItem label="Tall" pct={summary.speciesDistribution.pinePct} color="bg-orange-500" />
                    <SpeciesItem label="Gran" pct={summary.speciesDistribution.sprucePct} color="bg-green-600" />
                    <SpeciesItem label="Löv" pct={summary.speciesDistribution.deciduousPct} color="bg-lime-500" />
                    <SpeciesItem label="Contorta" pct={summary.speciesDistribution.contortaPct} color="bg-amber-800" />
                  </div>
                </div>
              </div>
            )}

            {/* Target class distribution */}
            {summary?.targetClassDistribution && summary.targetClassDistribution.length > 0 && (
              <div className="rounded-xl border border-gray-200 bg-white">
                <div className="border-b border-gray-100 px-5 py-4">
                  <h2 className="text-sm font-semibold text-gray-800">Målklassfördelning</h2>
                </div>
                <div className="p-5 space-y-3">
                  {summary.targetClassDistribution.map((tc) => {
                    const pct = totalStandsArea > 0 ? (tc.areaHa / totalStandsArea) * 100 : 0;
                    return (
                      <div key={tc.targetClass} className="flex items-center gap-3">
                        <div className={`h-3 w-3 rounded-full ${TARGET_CLASS_COLORS[tc.targetClass] ?? 'bg-gray-400'}`} />
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-gray-700">
                              {tc.targetClass} – {TARGET_CLASS_LABELS[tc.targetClass] ?? tc.targetClass}
                            </span>
                            <span className="text-xs text-gray-500">
                              {tc.areaHa.toFixed(1)} ha ({pct.toFixed(1)}%)
                            </span>
                          </div>
                          <div className="mt-1 h-2 w-full rounded-full bg-gray-100">
                            <div
                              className={`h-full rounded-full ${TARGET_CLASS_COLORS[tc.targetClass] ?? 'bg-gray-400'}`}
                              style={{ width: `${Math.min(pct, 100)}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Age class distribution */}
            {summary?.ageClassDistribution && summary.ageClassDistribution.length > 0 && (
              <div className="rounded-xl border border-gray-200 bg-white">
                <div className="border-b border-gray-100 px-5 py-4">
                  <h2 className="text-sm font-semibold text-gray-800">Åldersklassfördelning</h2>
                </div>
                <div className="p-5">
                  <div className="space-y-2">
                    {summary.ageClassDistribution.map((ac) => {
                      const pct = totalStandsArea > 0 ? (ac.areaHa / totalStandsArea) * 100 : 0;
                      return (
                        <div key={ac.ageClass} className="flex items-center gap-2">
                          <span className="w-14 text-right text-xs text-gray-600">{ac.ageClass}</span>
                          <div className="flex-1 h-5 rounded bg-gray-100">
                            <div
                              className="h-full rounded bg-forest-500 transition-all"
                              style={{ width: `${Math.min(pct, 100)}%` }}
                            />
                          </div>
                          <span className="w-16 text-right text-xs text-gray-500">
                            {ac.areaHa.toFixed(1)} ha
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* Upcoming actions */}
            <div className="rounded-xl border border-gray-200 bg-white">
              <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
                <h2 className="text-sm font-semibold text-gray-800">Kommande åtgärder (Period 1)</h2>
                {selectedPropertyId && (
                  <Link
                    to={`/properties/${selectedPropertyId}?tab=actions`}
                    className="text-xs font-medium text-forest-700 hover:text-forest-800"
                  >
                    Alla åtgärder
                  </Link>
                )}
              </div>
              <div className="divide-y divide-gray-50">
                {actionsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                  </div>
                ) : urgentActions.length === 0 ? (
                  <div className="py-8 text-center text-sm text-gray-400">
                    Inga brådskande åtgärder
                  </div>
                ) : (
                  urgentActions.slice(0, 6).map((action) => (
                    <div
                      key={action.standId}
                      className="flex items-center justify-between px-5 py-3"
                    >
                      <div className="flex items-center gap-3">
                        <span
                          className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white ${
                            action.urgency === 1
                              ? 'bg-red-500'
                              : action.urgency === 2
                                ? 'bg-orange-500'
                                : 'bg-yellow-500'
                          }`}
                        >
                          {action.standNumber}
                        </span>
                        <div>
                          <p className="text-sm font-medium text-gray-800">
                            {ACTION_LABELS[action.action] ?? action.action}
                          </p>
                          <p className="text-xs text-gray-500">
                            {action.areaHa?.toFixed(1)} ha
                            {action.actionYear ? ` · År ${action.actionYear}` : ''}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        {action.netValueSek != null && action.netValueSek !== 0 && (
                          <p className="text-sm font-medium text-forest-700">
                            {formatSEK(action.netValueSek)} kr
                          </p>
                        )}
                        <p className="text-xs text-gray-400">Prio {action.urgency}</p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Economic summary */}
            {economicData && (
              <div className="rounded-xl border border-gray-200 bg-white">
                <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
                  <h2 className="text-sm font-semibold text-gray-800">Ekonomisk översikt</h2>
                  {selectedPropertyId && (
                    <Link
                      to={`/properties/${selectedPropertyId}?tab=economy`}
                      className="text-xs font-medium text-forest-700 hover:text-forest-800"
                    >
                      Detaljer
                    </Link>
                  )}
                </div>
                <div className="p-5 space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <EconItem label="Timmer" value={`${Math.round(economicData.totalTimberVolumeM3)} m³fub`} />
                    <EconItem label="Massaved" value={`${Math.round(economicData.totalPulpwoodVolumeM3)} m³fub`} />
                    <EconItem label="Bruttovärde" value={`${formatSEK(economicData.totalGrossValueSek)} kr`} />
                    <EconItem label="Avverkningskostnad" value={`-${formatSEK(economicData.totalHarvestingCostSek)} kr`} muted />
                  </div>
                  <div className="rounded-lg bg-forest-50 p-3">
                    <p className="text-xs text-forest-700 uppercase tracking-wide">Nettovärde</p>
                    <p className="text-xl font-bold text-forest-800">
                      {formatSEK(economicData.totalNetValueSek)} kr
                    </p>
                  </div>
                  {economicData.totalNpv10yr > 0 && (
                    <p className="text-xs text-gray-500">
                      NPV (10 år, 2.5% diskontering): {formatSEK(economicData.totalNpv10yr)} kr
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Plans for this property */}
            <div className="rounded-xl border border-gray-200 bg-white">
              <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
                <h2 className="text-sm font-semibold text-gray-800">Skogsbruksplaner</h2>
                {selectedPropertyId && (
                  <Link
                    to={`/properties/${selectedPropertyId}?tab=plan`}
                    className="text-xs font-medium text-forest-700 hover:text-forest-800"
                  >
                    Hantera planer
                  </Link>
                )}
              </div>
              <div className="divide-y divide-gray-50">
                {propertyPlans.length === 0 ? (
                  <div className="py-8 text-center text-sm text-gray-400">
                    Ingen skogsbruksplan skapad för denna fastighet
                  </div>
                ) : (
                  propertyPlans.map((plan: ForestPlan) => (
                    <div
                      key={plan.id}
                      className="flex items-center justify-between px-5 py-3"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="h-4 w-4 text-forest-600" />
                        <div>
                          <p className="text-sm font-medium text-gray-800">{plan.name}</p>
                          <p className="text-xs text-gray-500">
                            Version {plan.version}
                            {plan.validFrom && plan.validTo
                              ? ` · ${plan.validFrom} – ${plan.validTo}`
                              : ''}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            plan.status === 'published'
                              ? 'bg-green-100 text-green-800'
                              : plan.status === 'draft'
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-gray-100 text-gray-600'
                          }`}
                        >
                          {plan.status === 'published' ? 'Publicerad' : plan.status === 'draft' ? 'Utkast' : 'Arkiverad'}
                        </span>
                        {plan.certification && plan.certification !== 'none' && (
                          <span title={plan.certification}><Shield className="h-4 w-4 text-forest-600" /></span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recent properties list */}
        <div className="rounded-xl border border-gray-200 bg-white">
          <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
            <h2 className="text-sm font-semibold text-gray-800">Senaste fastigheter</h2>
            <Link to="/properties" className="text-xs font-medium text-forest-700 hover:text-forest-800">
              Visa alla
            </Link>
          </div>
          <div className="divide-y divide-gray-50">
            {propertiesLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            ) : properties.length === 0 ? (
              <div className="py-8 text-center text-sm text-gray-400">
                Inga fastigheter ännu
              </div>
            ) : (
              properties.slice(0, 5).map((property) => (
                <Link
                  key={property.id}
                  to={`/properties/${property.id}`}
                  className="flex items-center justify-between px-5 py-3 transition hover:bg-gray-50"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-800">{property.name}</p>
                    <p className="text-xs text-gray-500">
                      {property.propertyDesignation} &middot; {property.municipality}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-500">
                      {property.totalArea?.toFixed(1)} ha
                    </span>
                    <ArrowRight className="h-4 w-4 text-gray-400" />
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Mini map */}
        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          <div className="border-b border-gray-100 px-5 py-4">
            <h2 className="text-sm font-semibold text-gray-800">Översiktskarta</h2>
          </div>
          <MiniMap properties={properties} />
        </div>
      </div>
    </div>
  );
}

/* ── Helpers ── */

function formatSEK(value: number): string {
  return Math.round(value).toLocaleString('sv-SE');
}

/* ───────── Quick action card ───────── */

function QuickActionCard({
  icon,
  title,
  description,
  onClick,
  color,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
  color: string;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 text-left shadow-sm transition hover:shadow-md"
    >
      <div className={`rounded-lg p-3 ${color}`}>{icon}</div>
      <div>
        <p className="text-sm font-semibold text-gray-800">{title}</p>
        <p className="text-xs text-gray-500">{description}</p>
      </div>
    </button>
  );
}

/* ───────── Stat card ───────── */

function StatCard({
  label,
  value,
  icon,
  highlight,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div className={`rounded-xl border bg-white p-4 shadow-sm ${highlight ? 'border-amber-300' : 'border-gray-200'}`}>
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2 ${highlight ? 'bg-amber-50 text-amber-700' : 'bg-forest-50 text-forest-700'}`}>
          {icon}
        </div>
        <div>
          <p className={`text-2xl font-bold ${highlight ? 'text-amber-700' : 'text-gray-900'}`}>{value}</p>
          <p className="text-xs text-gray-500">{label}</p>
        </div>
      </div>
    </div>
  );
}

/* ───────── Metric card (small key figure) ───────── */

function MetricCard({
  label,
  value,
  unit,
  icon,
}: {
  label: string;
  value: string;
  unit: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex items-center gap-2 text-gray-500 mb-1">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <p className="text-lg font-bold text-gray-900">
        {value} <span className="text-xs font-normal text-gray-500">{unit}</span>
      </p>
    </div>
  );
}

/* ───────── Species bar ───────── */

function SpeciesBar({ distribution }: { distribution: { pine: number; spruce: number; deciduous: number; contorta: number } }) {
  const total = distribution.pine + distribution.spruce + distribution.deciduous + distribution.contorta;
  if (total === 0) return <div className="h-6 rounded-full bg-gray-100" />;

  return (
    <div className="flex h-6 overflow-hidden rounded-full">
      {distribution.pine > 0 && (
        <div
          className="bg-orange-500 flex items-center justify-center text-xs font-medium text-white"
          style={{ width: `${(distribution.pine / total) * 100}%` }}
        >
          {distribution.pine >= 10 ? `${distribution.pine.toFixed(0)}%` : ''}
        </div>
      )}
      {distribution.spruce > 0 && (
        <div
          className="bg-green-600 flex items-center justify-center text-xs font-medium text-white"
          style={{ width: `${(distribution.spruce / total) * 100}%` }}
        >
          {distribution.spruce >= 10 ? `${distribution.spruce.toFixed(0)}%` : ''}
        </div>
      )}
      {distribution.deciduous > 0 && (
        <div
          className="bg-lime-500 flex items-center justify-center text-xs font-medium text-white"
          style={{ width: `${(distribution.deciduous / total) * 100}%` }}
        >
          {distribution.deciduous >= 10 ? `${distribution.deciduous.toFixed(0)}%` : ''}
        </div>
      )}
      {distribution.contorta > 0 && (
        <div
          className="bg-amber-800 flex items-center justify-center text-xs font-medium text-white"
          style={{ width: `${(distribution.contorta / total) * 100}%` }}
        >
          {distribution.contorta >= 10 ? `${distribution.contorta.toFixed(0)}%` : ''}
        </div>
      )}
    </div>
  );
}

function SpeciesItem({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`h-3 w-3 rounded-full ${color}`} />
      <span className="text-sm text-gray-700">{label}</span>
      <span className="ml-auto text-sm font-medium text-gray-900">{pct.toFixed(1)}%</span>
    </div>
  );
}

/* ───────── Economic item ───────── */

function EconItem({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-sm font-medium ${muted ? 'text-red-600' : 'text-gray-900'}`}>{value}</p>
    </div>
  );
}

/* ───────── Alert card ───────── */

const SEVERITY_STYLES: Record<string, { bg: string; border: string; icon: string; badge: string }> = {
  critical: { bg: 'bg-red-50', border: 'border-red-200', icon: 'text-red-600', badge: 'bg-red-100 text-red-800' },
  warning: { bg: 'bg-amber-50', border: 'border-amber-200', icon: 'text-amber-600', badge: 'bg-amber-100 text-amber-800' },
  info: { bg: 'bg-blue-50', border: 'border-blue-200', icon: 'text-blue-600', badge: 'bg-blue-100 text-blue-800' },
  success: { bg: 'bg-green-50', border: 'border-green-200', icon: 'text-green-600', badge: 'bg-green-100 text-green-800' },
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  storm: <Wind className="h-4 w-4" />,
  bark_beetle: <Bug className="h-4 w-4" />,
  frost: <Thermometer className="h-4 w-4" />,
  heavy_rain: <CloudRain className="h-4 w-4" />,
  harvesting: <TreePine className="h-4 w-4" />,
  thinning: <TreePine className="h-4 w-4" />,
  regeneration: <TreePine className="h-4 w-4" />,
  growth: <TrendingUp className="h-4 w-4" />,
  certification: <Shield className="h-4 w-4" />,
  seasonal: <Info className="h-4 w-4" />,
};

function AlertCard({ alert }: { alert: AlertItemApi }) {
  const style = SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.info;
  const icon = CATEGORY_ICONS[alert.category] ?? <Info className="h-4 w-4" />;

  return (
    <div className={`flex gap-3 px-5 py-3 ${style.bg}`}>
      <div className={`mt-0.5 flex-shrink-0 ${style.icon}`}>{icon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-sm font-semibold text-gray-900">{alert.title}</p>
          <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold uppercase ${style.badge}`}>
            {alert.severity === 'critical' ? 'Kritisk' : alert.severity === 'warning' ? 'Varning' : alert.severity === 'success' ? 'OK' : 'Info'}
          </span>
        </div>
        <p className="text-xs text-gray-600 mt-0.5 leading-relaxed">{alert.message}</p>
        {alert.affectedStands && alert.affectedStands.filter(Boolean).length > 0 && (
          <p className="text-xs text-gray-500 mt-1">
            Avd: {alert.affectedStands.filter(Boolean).join(', ')}
          </p>
        )}
        {alert.action && (
          <p className="text-xs font-medium text-forest-700 mt-1">{alert.action}</p>
        )}
      </div>
    </div>
  );
}

/* ───────── Weather stat ───────── */

function WeatherStat({
  icon,
  label,
  value,
  warning,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  warning?: boolean;
}) {
  return (
    <div className={`rounded-lg p-3 ${warning ? 'bg-red-50 ring-1 ring-red-200' : 'bg-gray-50'}`}>
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p className={`text-sm font-bold ${warning ? 'text-red-700' : 'text-gray-900'}`}>
        {value}
      </p>
    </div>
  );
}

/* ───────── Mini map showing all properties ───────── */

function MiniMap({ properties }: { properties: { id: string; name: string; boundaryGeojson: any }[] }) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

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
      center: [15.5, 62.0],
      zoom: 4,
      interactive: true,
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const onLoad = () => {
      properties.forEach((property) => {
        if (property.boundaryGeojson?.features?.[0]) {
          try {
            const feature = property.boundaryGeojson.features[0];
            const coords = feature.geometry?.coordinates;
            if (coords) {
              const ring = Array.isArray(coords[0]?.[0]) ? coords[0][0] : coords[0];
              if (ring && ring.length > 0) {
                const lng = ring.reduce((s: number, c: number[]) => s + c[0], 0) / ring.length;
                const lat = ring.reduce((s: number, c: number[]) => s + c[1], 0) / ring.length;

                const el = document.createElement('div');
                el.style.width = '12px';
                el.style.height = '12px';
                el.style.borderRadius = '50%';
                el.style.backgroundColor = '#15803d';
                el.style.border = '2px solid white';
                el.style.boxShadow = '0 1px 4px rgba(0,0,0,0.3)';
                el.style.cursor = 'pointer';

                new maplibregl.Marker({ element: el })
                  .setLngLat([lng, lat])
                  .setPopup(new maplibregl.Popup({ offset: 12 }).setText(property.name))
                  .addTo(map);
              }
            }
          } catch {
            // skip properties without valid geometry
          }
        }
      });
    };

    if (map.loaded()) {
      onLoad();
    } else {
      map.on('load', onLoad);
    }
  }, [properties]);

  return <div ref={mapContainerRef} className="h-64" />;
}
