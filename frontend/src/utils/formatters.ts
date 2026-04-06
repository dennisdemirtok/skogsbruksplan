/**
 * Swedish formatting utilities for forest management data.
 * Uses Swedish locale conventions: comma as decimal separator,
 * space as thousands separator.
 */

/**
 * Format area in hectares.
 * @example formatArea(12.5) => "12,5 ha"
 */
export function formatArea(ha: number | null | undefined): string {
  if (ha == null || isNaN(ha)) return '-';
  return `${ha.toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ha`;
}

/**
 * Format volume per hectare.
 * @example formatVolume(245) => "245 m\u00b3sk/ha"
 */
export function formatVolume(m3perHa: number | null | undefined): string {
  if (m3perHa == null || isNaN(m3perHa)) return '-';
  return `${Math.round(m3perHa).toLocaleString('sv-SE')} m\u00b3sk/ha`;
}

/**
 * Format total volume.
 * @example formatTotalVolume(3500) => "3 500 m\u00b3sk"
 */
export function formatTotalVolume(m3: number | null | undefined): string {
  if (m3 == null || isNaN(m3)) return '-';
  return `${Math.round(m3).toLocaleString('sv-SE')} m\u00b3sk`;
}

/**
 * Format currency in Swedish kronor.
 * @example formatCurrency(125000) => "125 000 kr"
 */
export function formatCurrency(sek: number | null | undefined): string {
  if (sek == null || isNaN(sek)) return '-';
  return `${Math.round(sek).toLocaleString('sv-SE')} kr`;
}

/**
 * Format percentage.
 * @example formatPercent(45.3) => "45%"
 */
export function formatPercent(pct: number | null | undefined): string {
  if (pct == null || isNaN(pct)) return '-';
  return `${Math.round(pct)}%`;
}

/**
 * Format species composition as a compact string.
 * Uses Swedish abbreviations: T=Tall, G=Gran, L=Löv, C=Contorta
 * @example formatSpecies(60, 30, 10) => "T60 G30 L10"
 */
export function formatSpecies(
  pine: number,
  spruce: number,
  deciduous: number,
  contorta?: number,
): string {
  const parts: string[] = [];
  if (pine > 0) parts.push(`T${Math.round(pine)}`);
  if (spruce > 0) parts.push(`G${Math.round(spruce)}`);
  if (deciduous > 0) parts.push(`L${Math.round(deciduous)}`);
  if (contorta && contorta > 0) parts.push(`C${Math.round(contorta)}`);
  return parts.join(' ') || '-';
}

/**
 * Format a site index value.
 * @example formatSiteIndex('gran', 24) => "G24"
 */
export function formatSiteIndex(species: string, si: number): string {
  const prefix = species === 'tall' ? 'T' : species === 'gran' ? 'G' : species.charAt(0).toUpperCase();
  return `${prefix}${si}`;
}

/**
 * Format number with Swedish locale.
 * @example formatNumber(1234.5, 1) => "1 234,5"
 */
export function formatNumber(value: number | null | undefined, decimals = 0): string {
  if (value == null || isNaN(value)) return '-';
  return value.toLocaleString('sv-SE', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Format date in Swedish locale.
 * @example formatDate("2024-06-15T10:30:00Z") => "15 juni 2024"
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString('sv-SE', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/**
 * Format an action type to Swedish display name.
 */
export function formatActionType(action: string): string {
  const map: Record<string, string> = {
    slutavverkning: 'Slutavverkning',
    gallring: 'Gallring',
    rojning: 'Röjning',
    foryngring: 'Föryngring',
    ingen: 'Ingen åtgärd',
    naturvard: 'Naturvård',
    ovrig: 'Övrig',
  };
  return map[action] ?? action;
}

/**
 * Format a target class to Swedish display name.
 */
export function formatTargetClass(tc: string): string {
  const map: Record<string, string> = {
    PG: 'PG - Produktion, generell hänsyn',
    PF: 'PF - Produktion, förstärkt hänsyn',
    NS: 'NS - Naturvård, skötsel',
    NO: 'NO - Naturvård, orört',
    K: 'K - Kombinerat mål',
  };
  return map[tc] ?? tc;
}
