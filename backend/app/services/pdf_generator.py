import json
import logging
from datetime import date
from typing import Optional

from jinja2 import Template
from weasyprint import HTML

logger = logging.getLogger(__name__)

# ── Lowest harvesting age tables (duplicated from action_engine for self-containment) ──
PINE_LOWEST_HARVESTING_AGE = {
    32: 45, 30: 50, 28: 55, 26: 55, 24: 60,
    22: 65, 20: 70, 18: 80, 16: 90, 14: 100, 12: 110,
}
SPRUCE_LOWEST_HARVESTING_AGE = {
    36: 40, 34: 45, 32: 45, 30: 50, 28: 50, 26: 55,
    24: 60, 22: 65, 20: 70, 18: 75, 16: 85, 14: 95,
}

# SI-based annual growth estimates (m³sk / ha / year)
GROWTH_BY_SI = [
    (14, 2.0), (18, 3.0), (22, 4.5), (26, 6.0), (30, 7.5), (999, 9.0),
]

# Timber prices for economic breakdown (SEK / m³fub, 2024 averages)
TIMBER_PRICES = {
    "tall_timmer": 650, "gran_timmer": 600, "lov_timmer": 400,
    "tall_massaved": 350, "gran_massaved": 320, "lov_massaved": 300,
    "contorta_massaved": 310,
}

# Huggningsklass descriptions
HK_DESCRIPTIONS = {
    "K1": "Kalmark, ej föryngrad",
    "K2": "Kalmark, föryngrad",
    "R1": "Röjningsskog, ej röjningsbehov",
    "R2": "Röjningsskog, röjningsbehov",
    "G1": "Gallringsskog, ej gallrad",
    "G2": "Gallringsskog, gallrad",
    "S1": "Slutavverkningsskog, yngre",
    "S2": "Slutavverkningsskog, mogen",
    "S3": "Slutavverkningsskog, övermogen",
}

# Target class full names
TC_NAMES = {
    "PG": "Produktion med generell hänsyn",
    "PF": "Produktion med förstärkt hänsyn",
    "NS": "Naturvård, skötsel",
    "NO": "Naturvård, orörd",
}

# Action names in Swedish
ACTION_NAMES = {
    "slutavverkning": "Slutavverkning",
    "gallring": "Gallring",
    "rojning": "Röjning",
    "foryngring": "Föryngring",
    "ingen": "Ingen åtgärd",
}

# Short action names for compact table
ACTION_NAMES_SHORT = {
    "slutavverkning": "Slutavv.",
    "gallring": "Gallring",
    "rojning": "Röjning",
    "foryngring": "Föryngr.",
    "ingen": "Ingen",
}

# Glossary terms
GLOSSARY = [
    ("Avdelning", "En sammanhängande skogsyta med likartade egenskaper (trädslag, ålder, täthet)."),
    ("Skogsbruksplan", "10-årigt planeringsdokument för en skogsfastighet."),
    ("Slutavverkning", "Föryngringsavverkning (kalavverkning) av mogen skog."),
    ("Gallring", "Selektivt uttag av träd för att förbättra tillväxten hos kvarvarande bestånd."),
    ("Röjning", "Ungskogsröjning i tät ungskog för att skapa bättre förutsättningar."),
    ("Föryngring", "Åtgärder för att etablera ny skog (plantering, sådd eller naturlig föryngring)."),
    ("Bonitet (SI H100)", "Markens produktionsförmåga uttryckt som höjd i meter vid 100 års ålder."),
    ("Målklass", "Avdelningens skötselinriktning: PG, PF, NS eller NO."),
    ("PG", "Produktion med generell hänsyn – normal produktionsskog."),
    ("PF", "Produktion med förstärkt hänsyn – extra naturhänsyn."),
    ("NS", "Naturvård, skötsel – naturvård med aktiv skötsel."),
    ("NO", "Naturvård, orörd – lämnas utan åtgärd."),
    ("Grundyta (GY)", "Summan av trädstammarnas tvärsnittsarea per hektar (m²/ha)."),
    ("Virkesförråd", "Stående volym skog i m³sk (skogskubikmeter)."),
    ("m³sk", "Skogskubikmeter – volymmått på stående skog inklusive bark och topp."),
    ("m³fub", "Kubikmeter fast under bark – volymmått för avverkat virke."),
    ("Timmer", "Grovt virke (sågtimmer) med diameter ≥ 14 cm i topp."),
    ("Massaved", "Klenare virke som används till pappers- och massaindustrin."),
    ("Huggningsklass", "Beståndets utvecklingsstadium: K (kalmark), R (röjning), G (gallring), S (slutavverkning)."),
    ("Barkborre", "Granbarkborre (Ips typographus) – allvarlig skadeinsekt i granskog."),
    ("Hänsynsträd", "Träd som lämnas vid avverkning för biologisk mångfald."),
    ("Nyckelbiotop", "Skogsområde med höga naturvärden som ska bevaras."),
    ("Contorta", "Lodgepole pine (Pinus contorta) – nordamerikanskt trädslag."),
]


# ════════════════════════════════════════════════════════════════════════
#  JINJA2 HTML TEMPLATE
# ════════════════════════════════════════════════════════════════════════

PLAN_HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<style>
/* ── Page setup ────────────────────────────────────────────────── */
@page {
    size: A4;
    margin: 20mm 15mm 25mm 15mm;
    @top-center {
        content: "Skogsbruksplan – {{ property.designation }}";
        font-size: 8pt; color: #666;
    }
    @bottom-center {
        content: "Sida " counter(page) " av " counter(pages);
        font-size: 8pt; color: #666;
    }
}
@page :first { @top-center { content: ""; } @bottom-center { content: ""; } }

body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10pt; line-height: 1.45; color: #1a1a1a;
}

/* ── Headings ──────────────────────────────────────────────────── */
h1 { font-size: 22pt; color: #1b5e20; margin-bottom: 5mm; border-bottom: 2px solid #1b5e20; padding-bottom: 3mm; }
h2 { font-size: 14pt; color: #2e7d32; margin-top: 8mm; margin-bottom: 4mm; border-bottom: 1px solid #c8e6c9; padding-bottom: 2mm; }
h3 { font-size: 12pt; color: #388e3c; margin-top: 6mm; margin-bottom: 3mm; }
h4 { font-size: 10pt; color: #43a047; margin-top: 4mm; margin-bottom: 2mm; }

/* ── Cover page ────────────────────────────────────────────────── */
.cover-page { text-align: center; padding-top: 30mm; page-break-after: always; }
.cover-page h1 { font-size: 32pt; border: none; margin-bottom: 6mm; color: #1b5e20; }
.cover-page .subtitle { font-size: 18pt; color: #333; margin-bottom: 8mm; font-weight: 600; }
.cover-page .property-info { font-size: 12pt; margin-bottom: 3mm; color: #444; }
.cover-page .meta-info { font-size: 10pt; color: #777; margin-top: 25mm; }
.cover-line { width: 60mm; height: 3px; background: #2e7d32; margin: 10mm auto; border-radius: 2px; }
.cover-logo { width: 30mm; height: 30mm; border-radius: 50%; background: #1b5e20; color: #fff;
    font-size: 24pt; line-height: 30mm; text-align: center; margin: 0 auto 10mm; }
.cert-badge { display: inline-block; padding: 2mm 5mm; border-radius: 3mm; font-size: 9pt;
    font-weight: bold; margin: 0 2mm; }
.cert-fsc { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
.cert-pefc { background: #e3f2fd; color: #1565c0; border: 1px solid #90caf9; }

/* ── Tables ────────────────────────────────────────────────────── */
table { width: 100%; border-collapse: collapse; margin: 3mm 0; font-size: 8.5pt; }
th { background-color: #e8f5e9; color: #1b5e20; font-weight: bold; text-align: left;
    padding: 2mm 3mm; border: 0.5pt solid #a5d6a7; }
td { padding: 1.5mm 3mm; border: 0.5pt solid #c8e6c9; vertical-align: top; }
tr:nth-child(even) { background-color: #f1f8e9; }
.right { text-align: right; }
.center { text-align: center; }
.bold { font-weight: bold; }

/* ── TOC ───────────────────────────────────────────────────────── */
.toc { page-break-after: always; }
.toc ul { list-style: none; padding: 0; }
.toc li { padding: 2mm 0; border-bottom: 0.5pt dotted #c8e6c9; font-size: 11pt; }
.toc li span.num { display: inline-block; width: 8mm; font-weight: bold; color: #2e7d32; }

/* ── Species bar ───────────────────────────────────────────────── */
.species-bar { display: flex; height: 8mm; border-radius: 2mm; overflow: hidden; margin: 2mm 0; }
.species-pine { background-color: #ff9800; }
.species-spruce { background-color: #4caf50; }
.species-deciduous { background-color: #8bc34a; }
.species-contorta { background-color: #795548; }
.species-bar span { font-size: 7pt; color: #fff; line-height: 8mm; text-align: center; overflow: hidden; }

/* ── Bar chart (CSS-only horizontal bars) ──────────────────────── */
.bar-row { display: flex; align-items: center; margin: 1mm 0; }
.bar-label { width: 25mm; font-size: 8pt; text-align: right; padding-right: 2mm; color: #555; }
.bar-track { flex: 1; height: 6mm; background: #f5f5f5; border-radius: 1mm; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 1mm; }
.bar-fill-green { background: #4caf50; }
.bar-fill-blue { background: #42a5f5; }
.bar-fill-amber { background: #ffa726; }
.bar-fill-purple { background: #ab47bc; }
.bar-value { width: 18mm; font-size: 8pt; padding-left: 2mm; color: #555; }

/* ── Stand cards ───────────────────────────────────────────────── */
.stand-card { page-break-inside: avoid; border: 1px solid #c8e6c9; border-radius: 3mm;
    margin: 4mm 0; overflow: hidden; }
.stand-card-header { background: #e8f5e9; padding: 3mm 4mm; display: flex;
    justify-content: space-between; align-items: center; }
.stand-card-header h4 { margin: 0; color: #1b5e20; font-size: 11pt; }
.stand-card-body { padding: 3mm 4mm; }
.stand-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2mm; margin: 2mm 0; }
.stand-grid-item .label { font-size: 7pt; color: #888; text-transform: uppercase; }
.stand-grid-item .val { font-size: 11pt; font-weight: bold; color: #1b5e20; }
.stand-action { margin-top: 2mm; padding: 2mm 3mm; background: #fff8e1; border-left: 3px solid #ff9800;
    font-size: 9pt; border-radius: 0 2mm 2mm 0; }
.stand-notes { margin-top: 2mm; font-size: 8pt; color: #666; font-style: italic; }

/* ── Badges ────────────────────────────────────────────────────── */
.badge { display: inline-block; padding: 1mm 3mm; border-radius: 2mm; font-size: 8pt; font-weight: bold; }
.badge-pg { background: #e8f5e9; color: #2e7d32; }
.badge-pf { background: #fff8e1; color: #f57f17; }
.badge-ns { background: #e3f2fd; color: #1565c0; }
.badge-no { background: #f3e5f5; color: #7b1fa2; }
.badge-field { background: #e0f2f1; color: #00695c; }

/* ── Urgency colours ───────────────────────────────────────────── */
.urgency-1 { background-color: #ffcdd2 !important; }
.urgency-2 { background-color: #ffe0b2 !important; }
.urgency-3 { background-color: #fff9c4 !important; }
.urgency-4 { background-color: #e8f5e9 !important; }
.urgency-5 { background-color: #f5f5f5 !important; }

/* ── Summary boxes ─────────────────────────────────────────────── */
.summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; margin: 4mm 0; }
.summary-box { border: 1px solid #a5d6a7; border-radius: 3mm; padding: 4mm; background-color: #f9fbe7; }
.summary-box .label { font-size: 8pt; color: #666; text-transform: uppercase; letter-spacing: 0.5pt; }
.summary-box .value { font-size: 16pt; font-weight: bold; color: #1b5e20; }
.summary-box .unit { font-size: 9pt; color: #888; }

/* ── Period header ─────────────────────────────────────────────── */
.period-header { background: #e8f5e9; padding: 2mm 4mm; border-radius: 2mm;
    font-weight: bold; color: #1b5e20; margin: 4mm 0 2mm; font-size: 11pt; }

/* ── Economics highlight ───────────────────────────────────────── */
.econ-highlight { margin: 4mm 0; padding: 4mm; border: 1px solid #a5d6a7;
    border-radius: 2mm; background-color: #f1f8e9; }

/* ── Checklist ─────────────────────────────────────────────────── */
.checklist-item { padding: 1.5mm 0; padding-left: 6mm; position: relative; font-size: 9pt; }
.checklist-item::before { content: "\2610"; position: absolute; left: 0; font-size: 11pt; }
.checklist-item.checked::before { content: "\2611"; color: #2e7d32; }

/* ── Utility ───────────────────────────────────────────────────── */
.page-break { page-break-before: always; }
.no-break { page-break-inside: avoid; }
.footer-note { font-size: 8pt; color: #999; margin-top: 10mm; border-top: 0.5pt solid #ddd; padding-top: 2mm; }
.muted { color: #888; }
.small { font-size: 8pt; }

/* ── Stand map ────────────────────────────────────────────────── */
.stand-map { margin: 3mm 0; }
.stand-map-placeholder { padding: 8mm; text-align: center; color: #999; font-style: italic;
    background: #fafafa; border: 1px dashed #ccc; border-radius: 3mm; margin: 3mm 0; }
</style>
</head>
<body>

{# ══════════════ 1. FÖRSÄTTSBLAD ══════════════ #}
<div class="cover-page">
    <div class="cover-logo">&#9650;</div>
    <h1>Skogsbruksplan</h1>
    <div class="cover-line"></div>
    <div class="subtitle">{{ property.designation }}</div>
    <div class="property-info">
        {% if property.municipality %}Kommun: {{ property.municipality }}{% endif %}
        {% if property.county %} &middot; Län: {{ property.county }}{% endif %}
    </div>
    <div class="property-info">
        {% if property.total_area_ha %}Total areal: {{ "%.1f"|format(property.total_area_ha) }} ha{% endif %}
        {% if property.productive_forest_ha %} &middot; Produktiv skogsmark: {{ "%.1f"|format(property.productive_forest_ha) }} ha{% endif %}
    </div>
    {% if plan.certification and plan.certification != 'none' %}
    <div style="margin-top: 6mm;">
        {% if plan.certification in ['FSC', 'both'] %}<span class="cert-badge cert-fsc">FSC</span>{% endif %}
        {% if plan.certification in ['PEFC', 'both'] %}<span class="cert-badge cert-pefc">PEFC</span>{% endif %}
    </div>
    {% endif %}
    <div class="meta-info">
        <p>{{ plan.name }} &middot; Version {{ plan.version }}</p>
        {% if plan.valid_from and plan.valid_to %}
        <p>Planperiod: {{ plan.valid_from }} &ndash; {{ plan.valid_to }}</p>
        {% endif %}
        <p>Upprättad av: {{ plan.planner_name or 'Okänd' }}</p>
        <p>Datum: {{ generation_date }}</p>
    </div>
</div>

{# ══════════════ 2. INNEHÅLLSFÖRTECKNING ══════════════ #}
<div class="toc">
    <h2>Innehållsförteckning</h2>
    <ul>
        <li><span class="num">&bull;</span> Så här använder du din skogsbruksplan</li>
        <li><span class="num">1.</span> Skogsägarens målsättning</li>
        <li><span class="num">2.</span> Fastighetsbeskrivning och avdelningskarta</li>
        <li><span class="num">3.</span> Sammanställning
            <ul style="padding-left: 10mm; margin-top: 1mm;">
                <li style="border: none; font-size: 10pt; padding: 1mm 0;">3a. Virkesförråd per trädslag</li>
                <li style="border: none; font-size: 10pt; padding: 1mm 0;">3b. Åldersklassfördelning</li>
                <li style="border: none; font-size: 10pt; padding: 1mm 0;">3c. Huggningsklassfördelning</li>
                <li style="border: none; font-size: 10pt; padding: 1mm 0;">3d. Målklassfördelning</li>
                <li style="border: none; font-size: 10pt; padding: 1mm 0;">3e. Bonitet och tillväxt</li>
            </ul>
        </li>
        <li><span class="num">4.</span> Avdelningsbeskrivning &ndash; sammanställning</li>
        <li><span class="num">5.</span> Avdelningsbeskrivning &ndash; detaljerade avdelningskort</li>
        <li><span class="num">6.</span> Åtgärdsförslag</li>
        <li><span class="num">7.</span> Ekonomisk sammanställning</li>
        <li><span class="num">8.</span> Naturvärdesbedömning</li>
        {% if plan.certification and plan.certification != 'none' %}
        <li><span class="num">9.</span> Certifieringskontroll</li>
        {% endif %}
        {% set svl_toc = '10' if (plan.certification and plan.certification != 'none') else '9' %}
        <li><span class="num">{{ svl_toc }}.</span> Skogsvårdslagen &ndash; viktiga bestämmelser</li>
        <li><span class="num">{{ (svl_toc|int + 1)|string }}.</span> Ordlista</li>
    </ul>
</div>

{# ══════════════ GUIDE: SÅ HÄR ANVÄNDER DU DIN SKOGSBRUKSPLAN ══════════════ #}
<h2>Så här använder du din skogsbruksplan</h2>

<p style="margin-bottom: 3mm;">
    Skogsbruksplanen är ett beslutsunderlag och planeringsdokument som visar hur din skog ser ut idag
    och ger förslag på vilka åtgärder som bör göras under den kommande 10-årsperioden. Planen är ett
    levande dokument som bör uppdateras efter utförda åtgärder.
</p>

<h3>Planens delar</h3>
<table>
    <tr><td class="bold" style="width: 35%;">Fastighetsbeskrivning</td>
        <td>Grundläggande uppgifter om din fastighet samt avdelningskarta som visar hur skogen delats in i avdelningar.</td></tr>
    <tr><td class="bold">Sammanställning</td>
        <td>Sammanfattning av skogens tillstånd: virkesförråd per trädslag, åldersklasser, huggningsklasser, målklasser, bonitet och tillväxt.</td></tr>
    <tr><td class="bold">Avdelningsbeskrivning</td>
        <td>Detaljerad beskrivning av varje avdelning med all uppmätt skogsdata. Presenteras både som tabell och som individuella avdelningskort.</td></tr>
    <tr><td class="bold">Åtgärdsförslag</td>
        <td>Föreslagna skogliga åtgärder uppdelade i Period 1 (år 1&ndash;5, brådskande) och Period 2 (år 6&ndash;10). Prioritet 1 = mest brådskande.</td></tr>
    <tr><td class="bold">Ekonomi</td>
        <td>Ekonomisk sammanställning med beräknade volymer per sortiment, priser och nettovärden.</td></tr>
    <tr><td class="bold">Naturvärden</td>
        <td>Bedömning av naturvärden, avsatt areal och barkborrerisk.</td></tr>
</table>

<h3>Viktiga begrepp i tabellerna</h3>
<table>
    <tr><td class="bold" style="width: 20%;">HK</td><td>Huggningsklass &ndash; beståndets utvecklingsstadium (K=kalmark, R=röjning, G=gallring, S=slutavverkning).</td></tr>
    <tr><td class="bold">MK / Målklass</td><td>PG = Produktion, PF = Förstärkt hänsyn, NS = Naturvård skötsel, NO = Naturvård orörd.</td></tr>
    <tr><td class="bold">SI</td><td>Ståndortsindex (bonitet) &ndash; markens produktionsförmåga. T = tall, G = gran. Siffran anger övre höjd vid 100 år.</td></tr>
    <tr><td class="bold">GY</td><td>Grundyta &ndash; trädstammarnas sammanlagda tvärsnittsarea per hektar (m²/ha).</td></tr>
    <tr><td class="bold">m³sk</td><td>Skogskubikmeter &ndash; stående volym inklusive bark och topp.</td></tr>
    <tr><td class="bold">m³fub</td><td>Kubikmeter fast under bark &ndash; volymmått för avverkat virke.</td></tr>
    <tr><td class="bold">Pr</td><td>Prioritet &ndash; åtgärdens brådskande (1 = omgående, 5 = ej aktuellt).</td></tr>
</table>

<p class="small muted" style="margin-top: 3mm;">
    <em>Observera att alla ekonomiska beräkningar är uppskattningar baserade på aktuella medelpriser
    och bör ses som vägledande. Kontakta din virkesköpare för aktuella priser.</em>
</p>

<div class="page-break"></div>

{# ══════════════ 3. SKOGSÄGARENS MÅLSÄTTNING ══════════════ #}
<h2>1. Skogsägarens målsättning</h2>
<p class="muted" style="font-style: italic; margin-bottom: 4mm;">
    Enligt PEFC-standarden ska skogsägarens mål med sitt skogsbruk dokumenteras.
    Fyll i relevanta målsättningar nedan.
</p>
<div style="margin-left: 4mm;">
    <div class="checklist-item">Hög ekonomisk avkastning och löpande intäkter</div>
    <div class="checklist-item">Långsiktigt värdetillväxt och kapitalbevarande</div>
    <div class="checklist-item">Naturvård och biologisk mångfald</div>
    <div class="checklist-item">Rekreation, jakt och friluftsliv</div>
    <div class="checklist-item">Aktivt och hållbart skogsbruk enligt certifieringskrav</div>
    <div class="checklist-item">Klimatnytta och koldioxidbindning</div>
</div>
<p class="small muted" style="margin-top: 4mm;">
    <em>Fylls i av skogsägaren i samråd med planläggaren.</em>
</p>

<div class="page-break"></div>

{# ══════════════ 4. FASTIGHETSBESKRIVNING ══════════════ #}
<h2>2. Fastighetsbeskrivning</h2>

<table>
    <tr><td class="bold" style="width: 40%;">Fastighetsbeteckning</td><td>{{ property.designation }}</td></tr>
    {% if property.municipality %}<tr><td class="bold">Kommun</td><td>{{ property.municipality }}</td></tr>{% endif %}
    {% if property.county %}<tr><td class="bold">Län</td><td>{{ property.county }}</td></tr>{% endif %}
    <tr><td class="bold">Antal avdelningar</td><td>{{ stands|length }}</td></tr>
    <tr><td class="bold">Total areal</td><td>{{ "%.1f"|format(total_area) }} ha</td></tr>
    <tr><td class="bold">Produktiv skogsmark</td><td>{{ "%.1f"|format(productive_area) }} ha</td></tr>
</table>

<h3>Ägoslag</h3>
<table>
    <tr>
        <th>Ägoslag</th><th class="right">Areal (ha)</th><th class="right">Andel (%)</th>
    </tr>
    {% for ag in agoslag %}
    <tr>
        <td>{{ ag.name }}</td>
        <td class="right">{{ "%.1f"|format(ag.area) }}</td>
        <td class="right">{{ "%.1f"|format(ag.pct) }}</td>
    </tr>
    {% endfor %}
    <tr class="bold">
        <td>Totalt</td>
        <td class="right">{{ "%.1f"|format(total_area) }}</td>
        <td class="right">100.0</td>
    </tr>
</table>

{# ── Avdelningskarta ── #}
<h3>Avdelningskarta</h3>
{% if stand_map_svg %}
<p class="small muted" style="margin-bottom: 2mm;">
    Avdelningsindelning färgkodad efter målklass. Siffror anger avdelningsnummer.
    Streckad linje visar fastighetsgräns.
</p>
<div class="stand-map">
{{ stand_map_svg }}
</div>
{% else %}
<div class="stand-map-placeholder">
    Avdelningskarta genereras automatiskt när avdelningsgeometrier finns registrerade i systemet.
</div>
{% endif %}

<div class="page-break"></div>

{# ══════════════ 5. SAMMANSTÄLLNING ══════════════ #}
<h2>3. Sammanställning</h2>

<div class="summary-grid">
    <div class="summary-box">
        <div class="label">Totalt virkesförråd</div>
        <div class="value">{{ "%.0f"|format(total_volume) }} <span class="unit">m³sk</span></div>
    </div>
    <div class="summary-box">
        <div class="label">Medelvolym</div>
        <div class="value">{{ "%.0f"|format(mean_volume_per_ha) }} <span class="unit">m³sk/ha</span></div>
    </div>
    <div class="summary-box">
        <div class="label">Medelålder (arealvägt)</div>
        <div class="value">{{ "%.0f"|format(weighted_age) }} <span class="unit">år</span></div>
    </div>
    <div class="summary-box">
        <div class="label">Medelbonitet (SI H100)</div>
        <div class="value">{{ "%.1f"|format(mean_site_index) }}</div>
    </div>
</div>

{# 5a. Virkesförråd per trädslag #}
<h3>3a. Virkesförråd per trädslag</h3>

{% if total_volume > 0 %}
<div class="species-bar">
    {% if vol_by_species.pine_vol > 0 %}<span class="species-pine" style="width: {{ "%.1f"|format(vol_by_species.pine_pct) }}%;">Tall {{ "%.0f"|format(vol_by_species.pine_pct) }}%</span>{% endif %}
    {% if vol_by_species.spruce_vol > 0 %}<span class="species-spruce" style="width: {{ "%.1f"|format(vol_by_species.spruce_pct) }}%;">Gran {{ "%.0f"|format(vol_by_species.spruce_pct) }}%</span>{% endif %}
    {% if vol_by_species.deciduous_vol > 0 %}<span class="species-deciduous" style="width: {{ "%.1f"|format(vol_by_species.deciduous_pct) }}%;">Löv {{ "%.0f"|format(vol_by_species.deciduous_pct) }}%</span>{% endif %}
    {% if vol_by_species.contorta_vol > 0 %}<span class="species-contorta" style="width: {{ "%.1f"|format(vol_by_species.contorta_pct) }}%;">Cont {{ "%.0f"|format(vol_by_species.contorta_pct) }}%</span>{% endif %}
</div>
{% endif %}

<table>
    <tr>
        <th>Trädslag</th><th class="right">Volym (m³sk)</th><th class="right">m³sk/ha</th><th class="right">Andel (%)</th>
    </tr>
    <tr><td>Tall</td><td class="right">{{ "%.0f"|format(vol_by_species.pine_vol) }}</td><td class="right">{{ "%.0f"|format(vol_by_species.pine_per_ha) }}</td><td class="right">{{ "%.1f"|format(vol_by_species.pine_pct) }}</td></tr>
    <tr><td>Gran</td><td class="right">{{ "%.0f"|format(vol_by_species.spruce_vol) }}</td><td class="right">{{ "%.0f"|format(vol_by_species.spruce_per_ha) }}</td><td class="right">{{ "%.1f"|format(vol_by_species.spruce_pct) }}</td></tr>
    <tr><td>Löv</td><td class="right">{{ "%.0f"|format(vol_by_species.deciduous_vol) }}</td><td class="right">{{ "%.0f"|format(vol_by_species.deciduous_per_ha) }}</td><td class="right">{{ "%.1f"|format(vol_by_species.deciduous_pct) }}</td></tr>
    <tr><td>Contorta</td><td class="right">{{ "%.0f"|format(vol_by_species.contorta_vol) }}</td><td class="right">{{ "%.0f"|format(vol_by_species.contorta_per_ha) }}</td><td class="right">{{ "%.1f"|format(vol_by_species.contorta_pct) }}</td></tr>
    <tr class="bold"><td>Totalt</td><td class="right">{{ "%.0f"|format(total_volume) }}</td><td class="right">{{ "%.0f"|format(mean_volume_per_ha) }}</td><td class="right">100.0</td></tr>
</table>

{# 5b. Åldersklassfördelning #}
<h3>3b. Åldersklassfördelning</h3>
<table>
    <tr>
        <th>Åldersklass</th><th class="right">Antal avd.</th><th class="right">Areal (ha)</th><th class="right">Andel (%)</th><th class="right">Medelvolym (m³sk/ha)</th>
    </tr>
    {% for ac in age_classes %}
    <tr>
        <td>{{ ac.label }}</td>
        <td class="right">{{ ac.count }}</td>
        <td class="right">{{ "%.1f"|format(ac.area) }}</td>
        <td class="right">{{ "%.1f"|format(ac.pct) }}</td>
        <td class="right">{{ "%.0f"|format(ac.mean_vol) }}</td>
    </tr>
    {% endfor %}
</table>

{% if age_classes %}
<div style="margin-top: 2mm;">
    {% for ac in age_classes %}
    <div class="bar-row">
        <div class="bar-label">{{ ac.label }}</div>
        <div class="bar-track"><div class="bar-fill bar-fill-green" style="width: {{ "%.1f"|format(ac.pct) }}%;"></div></div>
        <div class="bar-value">{{ "%.1f"|format(ac.area) }} ha</div>
    </div>
    {% endfor %}
</div>
{% endif %}

{# 5c. Huggningsklassfördelning #}
<h3>3c. Huggningsklassfördelning</h3>
<table>
    <tr>
        <th>HK</th><th>Beskrivning</th><th class="right">Antal avd.</th><th class="right">Areal (ha)</th><th class="right">Andel (%)</th>
    </tr>
    {% for hk in huggningsklass_summary %}
    <tr>
        <td class="bold">{{ hk.code }}</td>
        <td>{{ hk.description }}</td>
        <td class="right">{{ hk.count }}</td>
        <td class="right">{{ "%.1f"|format(hk.area) }}</td>
        <td class="right">{{ "%.1f"|format(hk.pct) }}</td>
    </tr>
    {% endfor %}
</table>

<div class="page-break"></div>

{# 5d. Målklassfördelning #}
<h3>3d. Målklassfördelning</h3>
<table>
    <tr>
        <th>Målklass</th><th>Beskrivning</th><th class="right">Antal avd.</th><th class="right">Areal (ha)</th><th class="right">Andel (%)</th>
    </tr>
    {% for tc in target_class_summary %}
    <tr>
        <td><span class="badge badge-{{ tc.target_class|lower }}">{{ tc.target_class }}</span></td>
        <td>{{ tc.description }}</td>
        <td class="right">{{ tc.count }}</td>
        <td class="right">{{ "%.1f"|format(tc.area) }}</td>
        <td class="right">{{ "%.1f"|format(tc.pct) }}</td>
    </tr>
    {% endfor %}
</table>

{% for tc in target_class_summary %}
<div class="bar-row">
    <div class="bar-label">{{ tc.target_class }}</div>
    <div class="bar-track"><div class="bar-fill {% if tc.target_class == 'PG' %}bar-fill-green{% elif tc.target_class == 'PF' %}bar-fill-amber{% elif tc.target_class == 'NS' %}bar-fill-blue{% else %}bar-fill-purple{% endif %}" style="width: {{ "%.1f"|format(tc.pct) }}%;"></div></div>
    <div class="bar-value">{{ "%.1f"|format(tc.pct) }}%</div>
</div>
{% endfor %}

{# 5e. Bonitet och tillväxt #}
<h3>3e. Bonitet och tillväxt</h3>
<table>
    <tr><td class="bold" style="width: 50%;">Medelbonitet (arealvägt SI H100)</td><td class="right">{{ "%.1f"|format(mean_site_index) }}</td></tr>
    <tr><td class="bold">Uppskattad årlig tillväxt</td><td class="right">{{ "%.1f"|format(annual_growth_per_ha) }} m³sk/ha/år</td></tr>
    <tr><td class="bold">Total årlig tillväxt (produktiv areal)</td><td class="right">{{ "%.0f"|format(annual_growth_total) }} m³sk/år</td></tr>
    <tr><td class="bold">Medelgrundyta (arealvägt)</td><td class="right">{{ "%.1f"|format(weighted_basal_area) }} m²/ha</td></tr>
    <tr><td class="bold">Medeldiameter (arealvägt)</td><td class="right">{{ "%.1f"|format(weighted_diameter) }} cm</td></tr>
    <tr><td class="bold">Medelhöjd (arealvägt)</td><td class="right">{{ "%.1f"|format(weighted_height) }} m</td></tr>
</table>

<div class="page-break"></div>

{# ══════════════ 6. AVDELNINGSBESKRIVNING – TABELL ══════════════ #}
<h2>4. Avdelningsbeskrivning &ndash; sammanställning</h2>

<table>
    <tr>
        <th>Avd</th><th class="right">Ha</th><th>HK</th>
        <th class="right">Ålder</th><th class="right">SI</th>
        <th class="right">H</th><th class="right">Ø</th><th class="right">GY</th>
        <th class="right">Vol/ha</th><th class="right">Vol</th>
        <th>T/G/L/C</th><th>MK</th><th>Åtgärd</th><th class="center">Pr</th>
    </tr>
    {% for s in stands_enriched %}
    <tr class="no-break{% if s.proposed_action and s.proposed_action != 'ingen' %} bold{% endif %}">
        <td>{{ s.stand_number }}</td>
        <td class="right">{{ "%.1f"|format(s.area_ha or 0) }}</td>
        <td class="center">{{ s.huggningsklass }}</td>
        <td class="right">{{ s.age_years or '-' }}</td>
        <td class="right">{{ s.si_formatted }}</td>
        <td class="right">{{ "%.1f"|format(s.mean_height_m or 0) }}</td>
        <td class="right">{{ "%.0f"|format(s.mean_diameter_cm or 0) }}</td>
        <td class="right">{{ "%.0f"|format(s.basal_area_m2 or 0) }}</td>
        <td class="right">{{ "%.0f"|format(s.volume_m3_per_ha or 0) }}</td>
        <td class="right">{{ "%.0f"|format(s.total_volume_m3 or 0) }}</td>
        <td>{{ "%.0f"|format(s.pine_pct or 0) }}/{{ "%.0f"|format(s.spruce_pct or 0) }}/{{ "%.0f"|format(s.deciduous_pct or 0) }}/{{ "%.0f"|format(s.contorta_pct or 0) }}</td>
        <td><span class="badge badge-{{ (s.target_class or 'pg')|lower }}">{{ s.target_class or '-' }}</span></td>
        <td>{{ action_names_short.get(s.proposed_action, s.proposed_action or '-') }}</td>
        <td class="center urgency-{{ s.action_urgency or 5 }}">{{ s.action_urgency or '-' }}</td>
    </tr>
    {% endfor %}
    <tr class="bold">
        <td>Totalt</td>
        <td class="right">{{ "%.1f"|format(stands_enriched|sum(attribute='area_ha') or 0) }}</td>
        <td colspan="7"></td>
        <td class="right">{{ "%.0f"|format(total_volume) }}</td>
        <td colspan="3"></td>
        <td></td>
    </tr>
</table>
<p class="footer-note">
    HK = Huggningsklass. MK = Målklass. Pr = Prioritet (1=brådskande, 5=ej aktuellt).
    T/G/L/C = Tall/Gran/Löv/Contorta %. GY = Grundyta (m²/ha). SI = Ståndortsindex H100 (T=tall, G=gran).
    H = Medelhöjd (m). Ø = Medeldiameter (cm). Vol/ha = m³sk/ha. Vol = Total volym m³sk.
</p>

<div class="page-break"></div>

{# ══════════════ 7. AVDELNINGSKORT ══════════════ #}
<h2>5. Avdelningsbeskrivning &ndash; detaljerade avdelningskort</h2>

{% for s in stands_enriched %}
<div class="stand-card no-break">
    <div class="stand-card-header">
        <h4>Avdelning {{ s.stand_number }}
            <span class="badge badge-{{ (s.target_class or 'pg')|lower }}" style="margin-left: 3mm;">{{ s.target_class or 'PG' }}</span>
            {% if s.field_verified %}<span class="badge badge-field" style="margin-left: 2mm;">Fältverifierad</span>{% endif %}
        </h4>
        <span style="font-size: 10pt; color: #555;">{{ "%.1f"|format(s.area_ha or 0) }} ha &middot; HK {{ s.huggningsklass }}</span>
    </div>
    <div class="stand-card-body">
        <div class="stand-grid">
            <div class="stand-grid-item"><div class="label">Ålder</div><div class="val">{{ s.age_years or '-' }} <span class="small muted">år</span></div></div>
            <div class="stand-grid-item"><div class="label">Bonitet (SI)</div><div class="val">{{ s.si_formatted }}</div></div>
            <div class="stand-grid-item"><div class="label">Volym</div><div class="val">{{ "%.0f"|format(s.volume_m3_per_ha or 0) }} <span class="small muted">m³sk/ha</span></div></div>
            <div class="stand-grid-item"><div class="label">Tot. volym</div><div class="val">{{ "%.0f"|format(s.total_volume_m3 or 0) }} <span class="small muted">m³sk</span></div></div>
            <div class="stand-grid-item"><div class="label">Höjd</div><div class="val">{{ "%.1f"|format(s.mean_height_m or 0) }} <span class="small muted">m</span></div></div>
            <div class="stand-grid-item"><div class="label">Diameter</div><div class="val">{{ "%.0f"|format(s.mean_diameter_cm or 0) }} <span class="small muted">cm</span></div></div>
            <div class="stand-grid-item"><div class="label">Grundyta</div><div class="val">{{ "%.0f"|format(s.basal_area_m2 or 0) }} <span class="small muted">m²/ha</span></div></div>
            <div class="stand-grid-item"><div class="label">Barkborrisk</div><div class="val">{% if s.bark_beetle_risk %}{{ "%.0f"|format((s.bark_beetle_risk or 0) * 100) }}%{% else %}-{% endif %}</div></div>
        </div>

        {# Species bar #}
        <div class="species-bar" style="margin-top: 2mm;">
            {% if (s.pine_pct or 0) > 0 %}<span class="species-pine" style="width: {{ "%.0f"|format(s.pine_pct or 0) }}%;">T {{ "%.0f"|format(s.pine_pct or 0) }}%</span>{% endif %}
            {% if (s.spruce_pct or 0) > 0 %}<span class="species-spruce" style="width: {{ "%.0f"|format(s.spruce_pct or 0) }}%;">G {{ "%.0f"|format(s.spruce_pct or 0) }}%</span>{% endif %}
            {% if (s.deciduous_pct or 0) > 0 %}<span class="species-deciduous" style="width: {{ "%.0f"|format(s.deciduous_pct or 0) }}%;">L {{ "%.0f"|format(s.deciduous_pct or 0) }}%</span>{% endif %}
            {% if (s.contorta_pct or 0) > 0 %}<span class="species-contorta" style="width: {{ "%.0f"|format(s.contorta_pct or 0) }}%;">C {{ "%.0f"|format(s.contorta_pct or 0) }}%</span>{% endif %}
        </div>

        {% if s.proposed_action and s.proposed_action != 'ingen' %}
        <div class="stand-action">
            <strong>Föreslagen åtgärd:</strong> {{ action_names.get(s.proposed_action, s.proposed_action) }}
            &middot; Prioritet {{ s.action_urgency or '-' }}
            {% if s.action_year %} &middot; Planerat år {{ s.action_year }}{% endif %}
            {% if s.net_value_sek %} &middot; Uppskattat netto: {{ "{:,.0f}".format(s.net_value_sek).replace(",", " ") }} kr{% endif %}
        </div>
        {% endif %}

        {% if s.notes %}
        <div class="stand-notes">{{ s.notes }}</div>
        {% endif %}
    </div>
</div>
{% endfor %}

<div class="page-break"></div>

{# ══════════════ 8. ÅTGÄRDSFÖRSLAG ══════════════ #}
<h2>6. Åtgärdsförslag</h2>

{% if period1_actions %}
<div class="period-header">Period 1 (år 1&ndash;5) &ndash; Brådskande och prioriterade åtgärder</div>
<table>
    <tr>
        <th>Avd</th><th class="right">Areal (ha)</th><th>Åtgärd</th>
        <th class="center">Pr</th><th class="center">År</th>
        <th class="right">Volym (m³sk)</th><th class="right">Netto (kr)</th>
    </tr>
    {% for s in period1_actions %}
    <tr>
        <td>{{ s.stand_number }}</td>
        <td class="right">{{ "%.1f"|format(s.area_ha or 0) }}</td>
        <td>{{ action_names.get(s.proposed_action, s.proposed_action) }}</td>
        <td class="center urgency-{{ s.action_urgency or 5 }}">{{ s.action_urgency or '-' }}</td>
        <td class="center">{{ s.action_year or '-' }}</td>
        <td class="right">{{ "%.0f"|format(s.total_volume_m3 or 0) }}</td>
        <td class="right">{{ "{:,.0f}".format(s.net_value_sek or 0).replace(",", " ") }}</td>
    </tr>
    {% endfor %}
    <tr class="bold">
        <td colspan="5">Summa period 1</td>
        <td class="right">{{ "%.0f"|format(period1_volume) }}</td>
        <td class="right">{{ "{:,.0f}".format(period1_net).replace(",", " ") }}</td>
    </tr>
</table>
{% else %}
<p class="muted">Inga brådskande åtgärder (prioritet 1&ndash;3) planerade under period 1.</p>
{% endif %}

{% if period2_actions %}
<div class="period-header">Period 2 (år 6&ndash;10) &ndash; Planerade åtgärder</div>
<table>
    <tr>
        <th>Avd</th><th class="right">Areal (ha)</th><th>Åtgärd</th>
        <th class="center">Pr</th><th class="center">År</th>
        <th class="right">Volym (m³sk)</th><th class="right">Netto (kr)</th>
    </tr>
    {% for s in period2_actions %}
    <tr>
        <td>{{ s.stand_number }}</td>
        <td class="right">{{ "%.1f"|format(s.area_ha or 0) }}</td>
        <td>{{ action_names.get(s.proposed_action, s.proposed_action) }}</td>
        <td class="center urgency-{{ s.action_urgency or 5 }}">{{ s.action_urgency or '-' }}</td>
        <td class="center">{{ s.action_year or '-' }}</td>
        <td class="right">{{ "%.0f"|format(s.total_volume_m3 or 0) }}</td>
        <td class="right">{{ "{:,.0f}".format(s.net_value_sek or 0).replace(",", " ") }}</td>
    </tr>
    {% endfor %}
    <tr class="bold">
        <td colspan="5">Summa period 2</td>
        <td class="right">{{ "%.0f"|format(period2_volume) }}</td>
        <td class="right">{{ "{:,.0f}".format(period2_net).replace(",", " ") }}</td>
    </tr>
</table>
{% endif %}

{% if not period1_actions and not period2_actions %}
<p>Inga åtgärder planerade under kommande 10-årsperiod.</p>
{% endif %}

{% if period1_actions or period2_actions %}
<div class="econ-highlight" style="margin-top: 4mm;">
    <table>
        <tr class="bold"><td>Totalt planerad avverkning (10 år)</td><td class="right">{{ "%.0f"|format(period1_volume + period2_volume) }} m³sk</td></tr>
        <tr class="bold"><td>Totalt uppskattat nettovärde</td><td class="right">{{ "{:,.0f}".format(period1_net + period2_net).replace(",", " ") }} kr</td></tr>
    </table>
</div>
{% endif %}

<div class="page-break"></div>

{# ══════════════ 9. EKONOMISK SAMMANSTÄLLNING ══════════════ #}
<h2>7. Ekonomisk sammanställning</h2>

{% if econ_breakdown %}
<h3>Sortimentsfördelning och värde</h3>
<table>
    <tr>
        <th>Sortiment</th><th class="right">Volym (m³fub)</th><th class="right">Pris (kr/m³fub)</th><th class="right">Värde (kr)</th>
    </tr>
    {% for row in econ_breakdown %}
    <tr>
        <td>{{ row.name }}</td>
        <td class="right">{{ "%.1f"|format(row.volume) }}</td>
        <td class="right">{{ row.price }}</td>
        <td class="right">{{ "{:,.0f}".format(row.value).replace(",", " ") }}</td>
    </tr>
    {% endfor %}
    <tr class="bold">
        <td>Summa bruttovärde</td>
        <td class="right">{{ "%.1f"|format(total_timber + total_pulpwood) }}</td>
        <td></td>
        <td class="right">{{ "{:,.0f}".format(total_gross_value).replace(",", " ") }}</td>
    </tr>
</table>

<div class="econ-highlight">
    <table>
        <tr><td>Bruttovärde</td><td class="right">{{ "{:,.0f}".format(total_gross_value).replace(",", " ") }} kr</td></tr>
        <tr><td>Avverkningskostnad</td><td class="right">&minus;{{ "{:,.0f}".format(total_harvesting_cost).replace(",", " ") }} kr</td></tr>
        <tr class="bold" style="font-size: 11pt;"><td>Nettovärde</td><td class="right">{{ "{:,.0f}".format(total_net_value).replace(",", " ") }} kr</td></tr>
    </table>
</div>

<p class="small muted" style="margin-top: 3mm;">
    Ekonomiska beräkningar baseras på genomsnittliga virkesprisnivåer 2024 och kan variera beroende
    på marknadsläge, sortimentsutfall och lokala förhållanden. Avverkningskostnader är uppskattade
    utifrån volym per hektar och arealstorlek. Alla volymer i m³fub (kubikmeter fast under bark).
</p>
{% else %}
<p class="muted">Inga avverkningsberäkningar tillgängliga (inga åtgärder planerade).</p>
{% endif %}

<div class="page-break"></div>

{# ══════════════ 10. NATURVÄRDESBEDÖMNING ══════════════ #}
<h2>8. Naturvärdesbedömning</h2>

<table>
    <tr><td class="bold" style="width: 55%;">Areal med naturvårdsmålklass (NS + NO)</td><td class="right">{{ "%.1f"|format(nature.ns_no_area) }} ha ({{ "%.1f"|format(nature.ns_no_pct) }}%)</td></tr>
    <tr><td class="bold">Antal avdelningar med NS/NO</td><td class="right">{{ nature.ns_no_count }}</td></tr>
    <tr><td class="bold">Areal med förstärkt hänsyn (PF)</td><td class="right">{{ "%.1f"|format(nature.pf_area) }} ha ({{ "%.1f"|format(nature.pf_pct) }}%)</td></tr>
    <tr><td class="bold">Total naturhänsyn (PF + NS + NO)</td><td class="right">{{ "%.1f"|format(nature.total_conservation_area) }} ha ({{ "%.1f"|format(nature.total_conservation_pct) }}%)</td></tr>
</table>

{% if nature.bark_beetle_stands %}
<h3>Barkborrerisk</h3>
<p>Följande avdelningar har förhöjd risk för granbarkborreangrepp (&gt; 40% risk):</p>
<table>
    <tr><th>Avd</th><th class="right">Areal (ha)</th><th class="right">Granandel (%)</th><th class="right">Risk</th></tr>
    {% for bb in nature.bark_beetle_stands %}
    <tr>
        <td>{{ bb.stand_number }}</td>
        <td class="right">{{ "%.1f"|format(bb.area_ha or 0) }}</td>
        <td class="right">{{ "%.0f"|format(bb.spruce_pct or 0) }}</td>
        <td class="right urgency-1">{{ "%.0f"|format((bb.bark_beetle_risk or 0) * 100) }}%</td>
    </tr>
    {% endfor %}
</table>
{% endif %}

{% if plan.certification and plan.certification != 'none' %}
<h3>Certifieringsuppfyllelse</h3>
<table>
    <tr><td class="bold">Krav: Minst 5% av produktiv areal som NS/NO (FSC)</td>
        <td class="right">{{ "%.1f"|format(nature.ns_no_pct) }}% &ndash; {% if nature.ns_no_pct >= 5.0 %}<span style="color: #2e7d32;">&#10003; Uppfyllt</span>{% else %}<span style="color: #c62828;">&#10007; Ej uppfyllt</span>{% endif %}</td></tr>
    <tr><td class="bold">Contortaandel av produktiv areal</td>
        <td class="right">{{ "%.1f"|format(nature.contorta_pct) }}% &ndash; {% if nature.contorta_pct < 20.0 %}<span style="color: #2e7d32;">&#10003; Under 20%</span>{% else %}<span style="color: #c62828;">&#10007; Överstiger 20%</span>{% endif %}</td></tr>
</table>
{% endif %}

{# ══════════════ 11. CERTIFIERINGSKONTROLL ══════════════ #}
{% if plan.certification and plan.certification != 'none' %}
<div class="page-break"></div>
<h2>9. Certifieringskontroll</h2>

{% if plan.certification in ['PEFC', 'both'] %}
<h3>PEFC-krav</h3>
<div style="margin-left: 2mm;">
    {% for item in cert_checks.pefc %}
    <div class="checklist-item{% if item.checked %} checked{% endif %}">{{ item.text }}</div>
    {% endfor %}
</div>
{% endif %}

{% if plan.certification in ['FSC', 'both'] %}
<h3>FSC-krav</h3>
<div style="margin-left: 2mm;">
    {% for item in cert_checks.fsc %}
    <div class="checklist-item{% if item.checked %} checked{% endif %}">{{ item.text }}</div>
    {% endfor %}
</div>
{% endif %}
{% endif %}

{# ══════════════ SKOGSVÅRDSLAGEN ══════════════ #}
<div class="page-break"></div>
{% set svl_num = '10' if (plan.certification and plan.certification != 'none') else '9' %}
<h2>{{ svl_num }}. Skogsvårdslagen &ndash; viktiga bestämmelser</h2>

<p style="margin-bottom: 3mm;">
    Skogsvårdslagen (1979:429) reglerar skogsbruket i Sverige. Nedan sammanfattas de viktigaste
    bestämmelserna som berör denna skogsbruksplan.
</p>

<h3>Föryngringsavverkning (6 &sect;)</h3>
<p>Skog som har uppnått lägsta tillåtna slutavverkningsålder enligt Skogsstyrelsens föreskrifter
får slutavverkas. Lägsta slutavverkningsålder varierar med bonitet och trädslag.
Anmälningsskyldighet gäller för avverkning av mer än 0,5 ha produktiv skogsmark (6 veckor före planerad avverkning).</p>

<h3>Föryngringsskyldighet (5 &sect;)</h3>
<p>Efter föryngringsavverkning ska ny skog anläggas senast tre år efter avverkning.
Godkänd föryngring ska vara uppnådd inom den tid som Skogsstyrelsen fastställer
(vanligen inom 7&ndash;10 år beroende på region och bonitet).</p>

<h3>Hänsyn till natur- och kulturmiljö (30 &sect;)</h3>
<p>Vid alla skogliga åtgärder ska hänsyn tas till naturvårdens och kulturmiljövårdens intressen.
Särskilt skyddsvärda biotoper, hänsynskrävande biotoper och kulturlämningar ska bevaras.
Kantzoner mot vatten ska lämnas orörda.</p>

<h3>Ransonering (10 &sect;)</h3>
<p>Årlig avverkning på en brukningsenhet bör inte under en 10-årsperiod överstiga fastighetens
tillväxt, om inte särskilda skäl föreligger.</p>

<h3>Röjningsskyldighet (9 &sect;)</h3>
<p>Skogsägaren ansvarar för att ungskog röjs vid behov så att skogens utveckling inte äventyras.</p>

<p class="small muted" style="margin-top: 4mm;">
    <em>Ovanstående är en förenklad sammanfattning. Fullständig lagtext och föreskrifter finns hos
    Skogsstyrelsen (skogsstyrelsen.se). Kontakta alltid Skogsstyrelsen vid osäkerhet om gällande regler.</em>
</p>

{# ══════════════ ORDLISTA ══════════════ #}
<div class="page-break"></div>
{% set glossary_num = (svl_num|int + 1)|string %}
<h2>{{ glossary_num }}. Ordlista</h2>

<table>
    <tr><th style="width: 30%;">Begrepp</th><th>Förklaring</th></tr>
    {% for term, desc in glossary %}
    <tr><td class="bold">{{ term }}</td><td>{{ desc }}</td></tr>
    {% endfor %}
</table>

{# ══════════════ FOOTER ══════════════ #}
<div class="footer-note" style="margin-top: 15mm;">
    <p>Denna skogsbruksplan har genererats av SkogsplanSaaS. Alla uppgifter baseras på
    tillgängliga skogliga grunddata och bör verifieras i fält. Ekonomiska beräkningar
    är uppskattningar baserade på aktuella medelpriser och kan variera beroende på
    marknadsläge och lokala förhållanden.</p>
    <p>Genererad: {{ generation_date }} &middot; SkogsplanSaaS &ndash; Digital skogsbruksplanering</p>
</div>

</body>
</html>
"""


# ════════════════════════════════════════════════════════════════════════
#  PDF GENERATOR CLASS
# ════════════════════════════════════════════════════════════════════════

class PDFGenerator:
    """Generates a professional Swedish skogsbruksplan (forest management plan) as PDF."""

    def __init__(self) -> None:
        self.template = Template(PLAN_HTML_TEMPLATE)

    # ── Public entry point ─────────────────────────────────────────────

    def generate_plan_pdf(
        self, plan: dict, property_data: dict, stands: list[dict],
        property_geojson: str = None,
    ) -> bytes:
        """Render the full skogsbruksplan and return PDF bytes."""

        # Basic aggregates
        stands_area = sum(s.get("area_ha", 0) or 0 for s in stands)
        total_area = property_data.get("total_area_ha") or stands_area
        productive_area = property_data.get("productive_forest_ha") or stands_area
        total_volume = sum(s.get("total_volume_m3", 0) or 0 for s in stands)
        mean_volume_per_ha = (total_volume / productive_area) if productive_area > 0 else 0

        # Area-weighted averages
        aw = self._area_weighted_averages(stands)
        weighted_age = aw.get("age_years", 0)
        mean_site_index = aw.get("site_index", 0)

        # Ägoslag
        agoslag = self._agoslag_breakdown(productive_area, total_area)

        # Volume by species
        vol_by_species = self._volume_by_species(stands, productive_area)

        # Age classes
        age_classes = self._age_class_distribution(stands, total_area)

        # Huggningsklass
        stands_enriched = self._enrich_stands(stands)
        huggningsklass_summary = self._huggningsklass_summary(stands_enriched, total_area)

        # Target class
        target_class_summary = self._target_class_summary(stands, total_area)

        # Growth
        annual_growth_per_ha = self._estimate_annual_growth_per_ha(mean_site_index)
        annual_growth_total = annual_growth_per_ha * productive_area

        # Additional weighted values
        weighted_basal_area = aw.get("basal_area_m2", 0)
        weighted_diameter = aw.get("mean_diameter_cm", 0)
        weighted_height = aw.get("mean_height_m", 0)

        # Actions by period
        action_stands = [
            s for s in stands_enriched
            if s.get("proposed_action") and s["proposed_action"] != "ingen"
        ]
        action_stands.sort(key=lambda x: x.get("action_urgency", 5) or 5)
        period1_actions, period2_actions = self._actions_by_period(action_stands)

        period1_volume = sum(s.get("total_volume_m3", 0) or 0 for s in period1_actions)
        period1_net = sum(s.get("net_value_sek", 0) or 0 for s in period1_actions)
        period2_volume = sum(s.get("total_volume_m3", 0) or 0 for s in period2_actions)
        period2_net = sum(s.get("net_value_sek", 0) or 0 for s in period2_actions)

        # Economics
        total_gross_value = sum(s.get("gross_value_sek", 0) or 0 for s in action_stands)
        total_harvesting_cost = sum(s.get("harvesting_cost_sek", 0) or 0 for s in action_stands)
        total_net_value = sum(s.get("net_value_sek", 0) or 0 for s in action_stands)
        total_timber = sum(s.get("timber_volume_m3", 0) or 0 for s in action_stands)
        total_pulpwood = sum(s.get("pulpwood_volume_m3", 0) or 0 for s in action_stands)
        econ_breakdown = self._economic_breakdown(action_stands)

        # Nature assessment
        nature = self._nature_value_assessment(stands, productive_area)

        # Certification
        cert_checks = self._certification_checks(stands, plan, productive_area)

        # Stand map SVG
        stand_map_svg = self._generate_stand_map_svg(stands, property_geojson)

        generation_date = date.today().isoformat()

        html_content = self.template.render(
            plan=plan,
            property=property_data,
            stands=stands,
            stands_enriched=stands_enriched,
            total_area=total_area,
            productive_area=productive_area,
            total_volume=total_volume,
            mean_volume_per_ha=mean_volume_per_ha,
            weighted_age=weighted_age,
            mean_site_index=mean_site_index,
            weighted_basal_area=weighted_basal_area,
            weighted_diameter=weighted_diameter,
            weighted_height=weighted_height,
            agoslag=agoslag,
            vol_by_species=vol_by_species,
            age_classes=age_classes,
            huggningsklass_summary=huggningsklass_summary,
            target_class_summary=target_class_summary,
            annual_growth_per_ha=annual_growth_per_ha,
            annual_growth_total=annual_growth_total,
            action_stands=action_stands,
            period1_actions=period1_actions,
            period2_actions=period2_actions,
            period1_volume=period1_volume,
            period1_net=period1_net,
            period2_volume=period2_volume,
            period2_net=period2_net,
            total_gross_value=total_gross_value,
            total_harvesting_cost=total_harvesting_cost,
            total_net_value=total_net_value,
            total_timber=total_timber,
            total_pulpwood=total_pulpwood,
            econ_breakdown=econ_breakdown,
            nature=nature,
            cert_checks=cert_checks,
            generation_date=generation_date,
            stand_map_svg=stand_map_svg,
            action_names=ACTION_NAMES,
            action_names_short=ACTION_NAMES_SHORT,
            glossary=GLOSSARY,
        )

        pdf_bytes = HTML(string=html_content).write_pdf()
        return pdf_bytes

    # ── Helper methods ─────────────────────────────────────────────────

    def _area_weighted_averages(self, stands: list[dict]) -> dict:
        """Compute area-weighted averages for numeric stand fields."""
        total_area = sum(s.get("area_ha", 0) or 0 for s in stands)
        if total_area == 0:
            return {f: 0 for f in [
                "age_years", "site_index", "pine_pct", "spruce_pct",
                "deciduous_pct", "contorta_pct", "basal_area_m2",
                "mean_diameter_cm", "mean_height_m",
            ]}

        fields = [
            "age_years", "site_index", "pine_pct", "spruce_pct",
            "deciduous_pct", "contorta_pct", "basal_area_m2",
            "mean_diameter_cm", "mean_height_m",
        ]
        result = {}
        for field in fields:
            weighted_sum = sum(
                (s.get(field, 0) or 0) * (s.get("area_ha", 0) or 0)
                for s in stands
            )
            result[field] = weighted_sum / total_area
        return result

    def _agoslag_breakdown(self, productive_area: float, total_area: float) -> list[dict]:
        """Estimate land-use (ägoslag) breakdown."""
        other = max(total_area - productive_area, 0)
        # Simple split: assume 70% of non-productive is impediment, rest water/other
        impediment = other * 0.7
        water_other = other * 0.3

        rows = [
            {"name": "Produktiv skogsmark", "area": productive_area,
             "pct": (productive_area / total_area * 100) if total_area > 0 else 0},
        ]
        if impediment > 0.05:
            rows.append({"name": "Impediment", "area": impediment,
                         "pct": (impediment / total_area * 100) if total_area > 0 else 0})
        if water_other > 0.05:
            rows.append({"name": "Övrig mark/vatten", "area": water_other,
                         "pct": (water_other / total_area * 100) if total_area > 0 else 0})
        return rows

    def _volume_by_species(self, stands: list[dict], productive_area: float) -> dict:
        """Break down total volume by species."""
        pine_vol = spruce_vol = dec_vol = cont_vol = 0.0
        for s in stands:
            tv = s.get("total_volume_m3", 0) or 0
            pine_vol += tv * ((s.get("pine_pct", 0) or 0) / 100)
            spruce_vol += tv * ((s.get("spruce_pct", 0) or 0) / 100)
            dec_vol += tv * ((s.get("deciduous_pct", 0) or 0) / 100)
            cont_vol += tv * ((s.get("contorta_pct", 0) or 0) / 100)

        total = pine_vol + spruce_vol + dec_vol + cont_vol
        pa = productive_area if productive_area > 0 else 1

        return {
            "pine_vol": pine_vol, "pine_per_ha": pine_vol / pa,
            "pine_pct": (pine_vol / total * 100) if total > 0 else 0,
            "spruce_vol": spruce_vol, "spruce_per_ha": spruce_vol / pa,
            "spruce_pct": (spruce_vol / total * 100) if total > 0 else 0,
            "deciduous_vol": dec_vol, "deciduous_per_ha": dec_vol / pa,
            "deciduous_pct": (dec_vol / total * 100) if total > 0 else 0,
            "contorta_vol": cont_vol, "contorta_per_ha": cont_vol / pa,
            "contorta_pct": (cont_vol / total * 100) if total > 0 else 0,
        }

    def _age_class_distribution(self, stands: list[dict], total_area: float) -> list[dict]:
        """Group stands into 20-year age classes."""
        classes = [
            (0, 20, "0–20"), (21, 40, "21–40"), (41, 60, "41–60"),
            (61, 80, "61–80"), (81, 100, "81–100"), (101, 120, "101–120"),
            (121, 9999, "121+"),
        ]
        results = []
        for lo, hi, label in classes:
            matching = [
                s for s in stands
                if lo <= (s.get("age_years") or 0) <= hi
            ]
            area = sum(s.get("area_ha", 0) or 0 for s in matching)
            vol_sum = sum(s.get("volume_m3_per_ha", 0) or 0 for s in matching)
            mean_vol = (vol_sum / len(matching)) if matching else 0
            pct = (area / total_area * 100) if total_area > 0 else 0
            results.append({
                "label": label, "count": len(matching),
                "area": area, "pct": pct, "mean_vol": mean_vol,
            })
        return results

    def _get_lowest_harvesting_age(
        self, site_index: float, pine_pct: float, spruce_pct: float
    ) -> Optional[int]:
        """Return the minimum legal harvesting age given SI and species mix."""
        si_rounded = round(site_index / 2) * 2
        table = PINE_LOWEST_HARVESTING_AGE if pine_pct >= spruce_pct else SPRUCE_LOWEST_HARVESTING_AGE
        if si_rounded in table:
            return table[si_rounded]
        closest = min(table.keys(), key=lambda x: abs(x - si_rounded))
        return table[closest]

    def _derive_huggningsklass(self, stand: dict) -> str:
        """Derive cutting class (huggningsklass) from stand data."""
        age = stand.get("age_years")
        vol = stand.get("volume_m3_per_ha", 0) or 0
        height = stand.get("mean_height_m")
        si = stand.get("site_index")
        pine = stand.get("pine_pct", 0) or 0
        spruce = stand.get("spruce_pct", 0) or 0

        # Kalmark
        if age is not None and age < 5 and vol < 10:
            return "K2" if vol > 0 else "K1"
        if age is None and vol < 10:
            return "K1"

        # Röjningsskog
        if height is not None and height < 3.0 and (age is None or age < 30):
            return "R1"
        if height is not None and 3.0 <= height <= 7.0 and (age is None or age < 35):
            return "R2"

        # Need SI for G/S classification
        if si is None or si <= 0:
            # Fallback: if young → G1, if old → S1
            if age is not None and age > 60:
                return "S1"
            return "G1"

        lowest_age = self._get_lowest_harvesting_age(si, pine, spruce)
        if lowest_age is None:
            return "G1"

        actual_age = age if age is not None else 0

        if actual_age < lowest_age:
            # Gallringsskog – use proposed action as hint for "gallrad"
            action = stand.get("proposed_action", "")
            if action == "gallring":
                return "G1"  # Needs thinning = not yet thinned
            return "G2" if actual_age > lowest_age * 0.6 else "G1"

        # Slutavverkningsskog
        ratio = actual_age / lowest_age if lowest_age > 0 else 1
        if ratio >= 1.5:
            return "S3"
        if ratio >= 1.2:
            return "S2"
        return "S1"

    def _format_si(self, stand: dict) -> str:
        """Format site index with species prefix (T=tall, G=gran), e.g. 'T24' or 'G28'."""
        si = stand.get("site_index")
        if si is None or si <= 0:
            return "-"
        pine = stand.get("pine_pct", 0) or 0
        spruce = stand.get("spruce_pct", 0) or 0
        prefix = "T" if pine >= spruce else "G"
        return f"{prefix}{si:.0f}"

    def _enrich_stands(self, stands: list[dict]) -> list[dict]:
        """Add derived huggningsklass and formatted SI to each stand dict."""
        enriched = []
        for s in stands:
            sc = dict(s)
            sc["huggningsklass"] = self._derive_huggningsklass(s)
            sc["si_formatted"] = self._format_si(s)
            enriched.append(sc)
        return enriched

    def _huggningsklass_summary(self, stands: list[dict], total_area: float) -> list[dict]:
        """Group stands by huggningsklass."""
        hk_map: dict[str, dict] = {}
        for s in stands:
            hk = s.get("huggningsklass", "G1")
            if hk not in hk_map:
                hk_map[hk] = {"count": 0, "area": 0.0}
            hk_map[hk]["count"] += 1
            hk_map[hk]["area"] += s.get("area_ha", 0) or 0

        order = ["K1", "K2", "R1", "R2", "G1", "G2", "S1", "S2", "S3"]
        results = []
        for code in order:
            if code in hk_map:
                area = hk_map[code]["area"]
                pct = (area / total_area * 100) if total_area > 0 else 0
                results.append({
                    "code": code,
                    "description": HK_DESCRIPTIONS.get(code, ""),
                    "count": hk_map[code]["count"],
                    "area": area,
                    "pct": pct,
                })
        return results

    def _target_class_summary(self, stands: list[dict], total_area: float) -> list[dict]:
        """Group stands by target class with descriptions."""
        tc_map: dict[str, dict] = {}
        for s in stands:
            tc = s.get("target_class", "PG") or "PG"
            if tc not in tc_map:
                tc_map[tc] = {"count": 0, "area": 0.0}
            tc_map[tc]["count"] += 1
            tc_map[tc]["area"] += s.get("area_ha", 0) or 0

        results = []
        for tc in ["PG", "PF", "NS", "NO"]:
            if tc in tc_map:
                pct = (tc_map[tc]["area"] / total_area * 100) if total_area > 0 else 0
                results.append({
                    "target_class": tc,
                    "description": TC_NAMES.get(tc, ""),
                    "count": tc_map[tc]["count"],
                    "area": tc_map[tc]["area"],
                    "pct": pct,
                })
        return results

    def _estimate_annual_growth_per_ha(self, mean_si: float) -> float:
        """Estimate annual growth (m³sk/ha/year) from area-weighted SI."""
        for threshold, growth in GROWTH_BY_SI:
            if mean_si < threshold:
                return growth
        return 9.0

    def _actions_by_period(
        self, action_stands: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """Split actions into period 1 (urgency 1-3) and period 2 (urgency 4+)."""
        p1 = [s for s in action_stands if (s.get("action_urgency") or 5) <= 3]
        p2 = [s for s in action_stands if (s.get("action_urgency") or 5) > 3]
        return p1, p2

    def _economic_breakdown(self, action_stands: list[dict]) -> list[dict]:
        """Break down economics by sortiment (species × product type)."""
        if not action_stands:
            return []

        # Accumulate volumes by species from all action stands
        pine_timber = spruce_timber = dec_timber = 0.0
        pine_pulp = spruce_pulp = dec_pulp = cont_pulp = 0.0

        for s in action_stands:
            timber_vol = s.get("timber_volume_m3", 0) or 0
            pulp_vol = s.get("pulpwood_volume_m3", 0) or 0
            total_fub = timber_vol + pulp_vol
            if total_fub <= 0:
                continue

            pine_frac = (s.get("pine_pct", 0) or 0) / 100
            spruce_frac = (s.get("spruce_pct", 0) or 0) / 100
            dec_frac = (s.get("deciduous_pct", 0) or 0) / 100
            cont_frac = (s.get("contorta_pct", 0) or 0) / 100

            pine_timber += timber_vol * pine_frac
            spruce_timber += timber_vol * spruce_frac
            dec_timber += timber_vol * dec_frac * 0.5  # Less timber from deciduous

            pine_pulp += pulp_vol * pine_frac
            spruce_pulp += pulp_vol * spruce_frac
            dec_pulp += pulp_vol * dec_frac
            cont_pulp += (timber_vol + pulp_vol) * cont_frac  # Contorta mostly pulp

        rows = []
        sortiments = [
            ("Tall timmer", pine_timber, TIMBER_PRICES["tall_timmer"]),
            ("Gran timmer", spruce_timber, TIMBER_PRICES["gran_timmer"]),
            ("Löv timmer", dec_timber, TIMBER_PRICES["lov_timmer"]),
            ("Tall massaved", pine_pulp, TIMBER_PRICES["tall_massaved"]),
            ("Gran massaved", spruce_pulp, TIMBER_PRICES["gran_massaved"]),
            ("Löv massaved", dec_pulp, TIMBER_PRICES["lov_massaved"]),
            ("Contorta massaved", cont_pulp, TIMBER_PRICES["contorta_massaved"]),
        ]
        for name, vol, price in sortiments:
            if vol > 0.05:
                rows.append({
                    "name": name, "volume": vol, "price": price,
                    "value": vol * price,
                })
        return rows

    def _nature_value_assessment(
        self, stands: list[dict], productive_area: float
    ) -> dict:
        """Assess nature values across the property."""
        ns_no_area = 0.0
        ns_no_count = 0
        pf_area = 0.0
        contorta_area = 0.0
        bark_beetle_stands = []

        for s in stands:
            tc = s.get("target_class", "PG") or "PG"
            area = s.get("area_ha", 0) or 0

            if tc in ("NS", "NO"):
                ns_no_area += area
                ns_no_count += 1
            elif tc == "PF":
                pf_area += area

            cont_pct = s.get("contorta_pct", 0) or 0
            contorta_area += area * (cont_pct / 100)

            bbr = s.get("bark_beetle_risk", 0) or 0
            if bbr > 0.4:
                bark_beetle_stands.append(s)

        pa = productive_area if productive_area > 0 else 1
        total_cons = ns_no_area + pf_area

        return {
            "ns_no_area": ns_no_area,
            "ns_no_pct": (ns_no_area / pa * 100),
            "ns_no_count": ns_no_count,
            "pf_area": pf_area,
            "pf_pct": (pf_area / pa * 100),
            "total_conservation_area": total_cons,
            "total_conservation_pct": (total_cons / pa * 100),
            "contorta_pct": (contorta_area / pa * 100) if pa > 0 else 0,
            "bark_beetle_stands": bark_beetle_stands,
        }

    def _certification_checks(
        self, stands: list[dict], plan: dict, productive_area: float
    ) -> dict:
        """Generate auto-checked certification items."""
        nature = self._nature_value_assessment(stands, productive_area)

        # Compute area-weighted contorta %
        aw = self._area_weighted_averages(stands)
        avg_contorta = aw.get("contorta_pct", 0)

        pefc_items = [
            {"text": "Skogsbruksplan upprättad och uppdaterad", "checked": True},
            {"text": "Skogsägarens målsättning dokumenterad", "checked": False},
            {"text": "Nyckelbiotoper identifierade och skyddade", "checked": False},
            {"text": f"Naturhänsyn vid avverkning (minst 5% av arealen) — nuvarande: {nature['ns_no_pct']:.1f}%",
             "checked": nature["ns_no_pct"] >= 5.0},
            {"text": "Kantzoner mot vatten (minst 5 m)", "checked": False},
            {"text": "Hänsynsträd lämnade (minst 10 st/ha vid föryngringsavverkning)", "checked": False},
            {"text": "Högstubbar skapade (minst 3 st/ha vid avverkning)", "checked": False},
            {"text": "Inga kemiska bekämpningsmedel utan dispens", "checked": False},
            {"text": f"Contortaandel understiger 20% av produktiv areal — nuvarande: {avg_contorta:.1f}%",
             "checked": avg_contorta < 20.0},
            {"text": "Kulturmiljöhänsyn dokumenterad", "checked": False},
            {"text": "Rödlistade arter beaktade", "checked": False},
        ]

        fsc_items = [
            {"text": f"Minst 5% av produktiv areal avsatt för naturvård (NS/NO) — nuvarande: {nature['ns_no_pct']:.1f}%",
             "checked": nature["ns_no_pct"] >= 5.0},
            {"text": "Nyckelbiotoper identifierade och bevarade", "checked": False},
            {"text": f"Inga planterade främmande trädarter >20% — contortaandel: {avg_contorta:.1f}%",
             "checked": avg_contorta < 20.0},
            {"text": "Kantzoner mot vatten och våtmarker respekterade", "checked": False},
            {"text": "Hänsynsytor vid föryngringsavverkning", "checked": False},
            {"text": "Kulturlämningar inventerade och skyddade", "checked": False},
            {"text": "Samråd med samebyar genomfört (om tillämpligt)", "checked": False},
            {"text": "Användning av kemiska bekämpningsmedel minimerad", "checked": False},
            {"text": "Arbetsmiljökrav uppfyllda", "checked": False},
            {"text": "Dokumentation av biologisk mångfald", "checked": False},
        ]

        return {"pefc": pefc_items, "fsc": fsc_items}

    # ── Stand map SVG ─────────────────────────────────────────────

    def _generate_stand_map_svg(
        self, stands: list[dict], property_geojson: str = None
    ) -> str:
        """Generate an SVG map of stands colored by target class.

        Returns SVG markup string, or empty string if no geometries exist.
        Coordinates are in SWEREF99 TM (meters), transformed to SVG viewport.
        """
        TC_COLORS = {
            "PG": ("#66bb6a", "#2e7d32"),
            "PF": ("#ffb74d", "#ef6c00"),
            "NS": ("#64b5f6", "#1565c0"),
            "NO": ("#ce93d8", "#6a1b9a"),
        }

        # ── Collect stand polygons ──
        stand_polys = []
        all_x: list[float] = []
        all_y: list[float] = []

        for s in stands:
            gj_str = s.get("geometry_geojson")
            if not gj_str:
                continue
            try:
                gj = json.loads(gj_str) if isinstance(gj_str, str) else gj_str
            except (json.JSONDecodeError, TypeError):
                continue

            geom_type = gj.get("type", "")
            coords = gj.get("coordinates", [])

            if geom_type == "Polygon":
                polys = [coords]
            elif geom_type == "MultiPolygon":
                polys = coords
            else:
                continue

            for poly_coords in polys:
                outer = poly_coords[0] if poly_coords else []
                for pt in outer:
                    all_x.append(pt[0])
                    all_y.append(pt[1])

            stand_polys.append({
                "polygons": polys,
                "stand_number": s.get("stand_number", "?"),
                "target_class": (s.get("target_class") or "PG").upper(),
            })

        # ── Parse property boundary ──
        prop_polys: list = []
        if property_geojson:
            try:
                pgj = json.loads(property_geojson) if isinstance(property_geojson, str) else property_geojson
                ptype = pgj.get("type", "")
                pcoords = pgj.get("coordinates", [])
                if ptype == "Polygon":
                    prop_polys = [pcoords]
                elif ptype == "MultiPolygon":
                    prop_polys = pcoords
                for poly_coords in prop_polys:
                    for ring in poly_coords:
                        for pt in ring:
                            all_x.append(pt[0])
                            all_y.append(pt[1])
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        if not all_x:
            return ""

        # ── Bounding box with padding ──
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        dx = max_x - min_x or 1
        dy = max_y - min_y or 1
        pad = max(dx, dy) * 0.06
        min_x -= pad
        max_x += pad
        min_y -= pad
        max_y += pad
        dx = max_x - min_x
        dy = max_y - min_y

        # SVG viewport dimensions (points, maps well to A4 width)
        svg_w = 680
        svg_h = max(250, min(700, int(svg_w * dy / dx)))

        def tx(x: float, y: float) -> str:
            """Transform geographic coords to SVG coords."""
            sx = (x - min_x) / dx * svg_w
            sy = svg_h - (y - min_y) / dy * svg_h  # flip Y
            return f"{sx:.1f},{sy:.1f}"

        lines: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {svg_w} {svg_h}" width="100%" '
            f'style="max-height: 250mm;">'
        ]

        # Background
        lines.append(
            f'<rect width="{svg_w}" height="{svg_h}" fill="#f5f7f0" rx="4"/>'
        )

        # ── Property boundary (dashed) ──
        for poly_coords in prop_polys:
            for ring in poly_coords:
                pts = " ".join(tx(p[0], p[1]) for p in ring)
                lines.append(
                    f'<polygon points="{pts}" fill="none" '
                    f'stroke="#555" stroke-width="2" stroke-dasharray="8,4"/>'
                )

        # ── Stand polygons ──
        for sp in stand_polys:
            tc = sp["target_class"]
            fill_c, stroke_c = TC_COLORS.get(tc, TC_COLORS["PG"])

            for poly_coords in sp["polygons"]:
                outer = poly_coords[0] if poly_coords else []
                if not outer:
                    continue
                pts = " ".join(tx(p[0], p[1]) for p in outer)
                lines.append(
                    f'<polygon points="{pts}" fill="{fill_c}" fill-opacity="0.55" '
                    f'stroke="{stroke_c}" stroke-width="1.5"/>'
                )
                # Inner rings (holes) as background color
                for hole in poly_coords[1:]:
                    hpts = " ".join(tx(p[0], p[1]) for p in hole)
                    lines.append(
                        f'<polygon points="{hpts}" fill="#f5f7f0" '
                        f'stroke="#555" stroke-width="0.5"/>'
                    )

        # ── Stand number labels ──
        for sp in stand_polys:
            all_rings = [p[0] for p in sp["polygons"] if p]
            if not all_rings:
                continue
            pts_flat = [pt for ring in all_rings for pt in ring[:-1]]
            if not pts_flat:
                continue
            cx = sum(p[0] for p in pts_flat) / len(pts_flat)
            cy = sum(p[1] for p in pts_flat) / len(pts_flat)
            sxy = tx(cx, cy)
            sx_s, sy_s = sxy.split(",")
            sx_f = float(sx_s)
            sy_f = float(sy_s)
            # White circle background for readability
            lines.append(
                f'<circle cx="{sx_f:.1f}" cy="{sy_f:.1f}" r="10" '
                f'fill="white" fill-opacity="0.85" stroke="#333" stroke-width="0.5"/>'
            )
            lines.append(
                f'<text x="{sx_f:.1f}" y="{sy_f + 1:.1f}" text-anchor="middle" '
                f'dominant-baseline="central" font-family="Arial,sans-serif" '
                f'font-size="9" font-weight="bold" fill="#1b5e20">'
                f'{sp["stand_number"]}</text>'
            )

        # ── Scale bar ──
        # SWEREF99 TM is in meters, so dx = map width in meters
        scale_m = dx
        nice = [50, 100, 200, 500, 1000, 2000, 5000, 10000]
        target_len = scale_m * 0.2
        bar_dist = min(nice, key=lambda d: abs(d - target_len))
        bar_w_svg = bar_dist / dx * svg_w
        bar_x = svg_w - bar_w_svg - 20
        bar_y = svg_h - 20

        lines.append(
            f'<rect x="{bar_x:.0f}" y="{bar_y:.0f}" '
            f'width="{bar_w_svg:.0f}" height="4" fill="#333"/>'
        )
        lines.append(
            f'<rect x="{bar_x:.0f}" y="{bar_y:.0f}" '
            f'width="1" height="8" fill="#333"/>'
        )
        lines.append(
            f'<rect x="{bar_x + bar_w_svg:.0f}" y="{bar_y:.0f}" '
            f'width="1" height="8" fill="#333"/>'
        )
        bar_label = f"{bar_dist // 1000} km" if bar_dist >= 1000 else f"{bar_dist} m"
        lines.append(
            f'<text x="{bar_x + bar_w_svg / 2:.0f}" y="{bar_y - 4:.0f}" '
            f'text-anchor="middle" font-family="Arial,sans-serif" '
            f'font-size="9" fill="#333">{bar_label}</text>'
        )

        # ── North arrow ──
        lines.append(
            '<text x="20" y="25" font-family="Arial,sans-serif" '
            'font-size="14" font-weight="bold" fill="#333">N</text>'
        )
        lines.append('<polygon points="23,28 20,40 26,40" fill="#333"/>')

        # ── Legend ──
        legend_x = 15
        legend_y = svg_h - 85
        lines.append(
            f'<rect x="{legend_x}" y="{legend_y}" width="130" height="72" '
            f'fill="white" fill-opacity="0.9" stroke="#ccc" rx="3"/>'
        )
        legend_items = [
            ("PG", "Produktion"),
            ("PF", "Förstärkt hänsyn"),
            ("NS", "Naturvård, skötsel"),
            ("NO", "Naturvård, orörd"),
        ]
        for i, (tc, label) in enumerate(legend_items):
            iy = legend_y + 10 + i * 15
            fill_c, _ = TC_COLORS.get(tc, TC_COLORS["PG"])
            lines.append(
                f'<rect x="{legend_x + 6}" y="{iy}" width="12" height="10" '
                f'fill="{fill_c}" fill-opacity="0.7" stroke="#333" '
                f'stroke-width="0.5" rx="1"/>'
            )
            lines.append(
                f'<text x="{legend_x + 24}" y="{iy + 8}" '
                f'font-family="Arial,sans-serif" font-size="8" fill="#333">'
                f'{label}</text>'
            )

        lines.append("</svg>")
        return "\n".join(lines)
