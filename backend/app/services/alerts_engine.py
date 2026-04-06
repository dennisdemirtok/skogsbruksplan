"""Smart alerts and recommendation engine for forest management.

Generates proactive, actionable alerts by combining:
- Stand data (species, age, volume, risk scores)
- Weather forecasts (storm risk, frost, precipitation)
- Seasonal context (bark beetle activity windows)
- Economic triggers (market timing, urgent harvesting)

This is what makes SkogsplanSaaS unique vs legacy tools like pcSKOG.
"""

import logging
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Severity levels ──
SEVERITY_CRITICAL = "critical"   # Red - immediate action needed
SEVERITY_WARNING = "warning"     # Orange - action recommended soon
SEVERITY_INFO = "info"           # Blue - good to know
SEVERITY_SUCCESS = "success"     # Green - positive status

# ── Alert categories ──
CATEGORY_STORM = "storm"
CATEGORY_BARK_BEETLE = "bark_beetle"
CATEGORY_FROST = "frost"
CATEGORY_HARVESTING = "harvesting"
CATEGORY_THINNING = "thinning"
CATEGORY_REGENERATION = "regeneration"
CATEGORY_GROWTH = "growth"
CATEGORY_CERTIFICATION = "certification"
CATEGORY_SEASONAL = "seasonal"

# ── Bark beetle temperature thresholds ──
# Granbarkborren (Ips typographus) swarms at >18°C, active development >15°C
BARK_BEETLE_SWARM_TEMP = 18.0
BARK_BEETLE_ACTIVE_TEMP = 15.0
BARK_BEETLE_MONTHS = [5, 6, 7, 8]  # May-August peak season

# ── SI-based lowest harvesting ages ──
PINE_HARVEST_AGE = {
    32: 45, 30: 50, 28: 55, 26: 55, 24: 60,
    22: 65, 20: 70, 18: 80, 16: 90, 14: 100, 12: 110,
}
SPRUCE_HARVEST_AGE = {
    36: 40, 34: 45, 32: 45, 30: 50, 28: 50, 26: 55,
    24: 60, 22: 65, 20: 70, 18: 75, 16: 85, 14: 95,
}


class AlertsEngine:
    """Generate smart, proactive alerts for forest management."""

    def generate_alerts(
        self,
        stands: list[dict],
        weather: Optional[dict] = None,
        property_data: Optional[dict] = None,
    ) -> list[dict]:
        """Generate all relevant alerts for a property.

        Args:
            stands: List of stand dicts with forest data
            weather: Optional weather forecast from SMHI
            property_data: Optional property metadata

        Returns:
            Sorted list of alert dicts with severity, category, title, message, etc.
        """
        alerts = []

        # Weather-based alerts
        if weather:
            alerts.extend(self._weather_alerts(weather, stands))

        # Stand-based alerts
        alerts.extend(self._bark_beetle_alerts(stands, weather))
        alerts.extend(self._harvesting_alerts(stands))
        alerts.extend(self._thinning_alerts(stands))
        alerts.extend(self._regeneration_alerts(stands))
        alerts.extend(self._growth_alerts(stands, property_data))
        alerts.extend(self._certification_alerts(stands, property_data))
        alerts.extend(self._seasonal_alerts(stands))

        # Sort by severity priority
        severity_order = {
            SEVERITY_CRITICAL: 0,
            SEVERITY_WARNING: 1,
            SEVERITY_INFO: 2,
            SEVERITY_SUCCESS: 3,
        }
        alerts.sort(key=lambda a: severity_order.get(a["severity"], 99))

        return alerts

    # ── Weather alerts ────────────────────────────────────────────

    def _weather_alerts(self, weather: dict, stands: list[dict]) -> list[dict]:
        """Generate alerts from weather forecast data."""
        alerts = []
        summary = weather.get("summary", {})

        max_wind = summary.get("max_wind_speed_ms", 0)
        max_gust = summary.get("max_wind_gust_ms", 0)
        total_precip = summary.get("total_precipitation_mm", 0)
        min_temp = summary.get("min_temperature_c", 0)
        max_temp = summary.get("max_temperature_c", 0)

        # Storm warning
        if max_gust >= 25:
            # Find vulnerable stands (tall spruce on shallow soils)
            vulnerable_stands = [
                s for s in stands
                if (s.get("spruce_pct", 0) or 0) >= 50
                and (s.get("mean_height_m", 0) or 0) >= 18
            ]
            avd_str = ", ".join(
                str(s.get("stand_number", "?")) for s in vulnerable_stands[:5]
            )
            alerts.append({
                "severity": SEVERITY_CRITICAL,
                "category": CATEGORY_STORM,
                "title": "Stormvarning – Hög vindrisk",
                "message": (
                    f"Vindbyar upp till {max_gust:.0f} m/s prognostiseras. "
                    f"{'Avdelning ' + avd_str + ' har hög granandel och höjd – extra utsatta.' if vulnerable_stands else 'Kontrollera höga granbestånd.'}"
                ),
                "affected_stands": [s.get("stand_number") for s in vulnerable_stands[:5]],
                "data": {"max_gust_ms": max_gust, "max_wind_ms": max_wind},
                "action": "Kontrollera utsatta bestånd efter stormen. Överväg vindskyddande gallring.",
            })
        elif max_gust >= 21:
            alerts.append({
                "severity": SEVERITY_WARNING,
                "category": CATEGORY_STORM,
                "title": "Kulingvarning",
                "message": (
                    f"Vindbyar upp till {max_gust:.0f} m/s väntas. "
                    "Var observant på riskträd vid skogsvägar."
                ),
                "affected_stands": [],
                "data": {"max_gust_ms": max_gust},
                "action": "Kontrollera stormkänsliga bestånd och riskträd vid vägar.",
            })

        # Heavy rain/snow
        if total_precip > 50:
            alerts.append({
                "severity": SEVERITY_WARNING,
                "category": CATEGORY_STORM,
                "title": "Kraftig nederbörd",
                "message": (
                    f"Totalt {total_precip:.0f} mm nederbörd väntas inom 48h. "
                    "Avvakta med avverkning – risk för körskador."
                ),
                "affected_stands": [],
                "data": {"total_precip_mm": total_precip},
                "action": "Skjut upp markberedning och avverkning vid mycket blöta förhållanden.",
            })
        elif total_precip > 30:
            alerts.append({
                "severity": SEVERITY_INFO,
                "category": CATEGORY_STORM,
                "title": "Regn väntas",
                "message": (
                    f"{total_precip:.0f} mm nederbörd väntas inom 48h. "
                    "Planera skogliga åtgärder med hänsyn till markfukt."
                ),
                "affected_stands": [],
                "data": {"total_precip_mm": total_precip},
                "action": None,
            })

        return alerts

    # ── Bark beetle alerts ────────────────────────────────────────

    def _bark_beetle_alerts(
        self, stands: list[dict], weather: Optional[dict] = None
    ) -> list[dict]:
        """Generate bark beetle risk alerts based on stand data, season and temperature."""
        alerts = []
        today = date.today()
        month = today.month

        # Find stands with high bark beetle risk
        high_risk = [
            s for s in stands
            if (s.get("bark_beetle_risk", 0) or 0) > 0.5
        ]
        moderate_risk = [
            s for s in stands
            if 0.3 < (s.get("bark_beetle_risk", 0) or 0) <= 0.5
        ]

        # Find susceptible stands (mature spruce, high volume)
        susceptible = [
            s for s in stands
            if (s.get("spruce_pct", 0) or 0) >= 60
            and (s.get("age_years", 0) or 0) >= 60
            and (s.get("volume_m3_per_ha", 0) or 0) >= 150
        ]

        # During bark beetle season
        if month in BARK_BEETLE_MONTHS:
            # Check if temperatures favor swarming
            warm_enough = False
            if weather:
                max_temp = weather.get("summary", {}).get("max_temperature_c", 0)
                warm_enough = max_temp >= BARK_BEETLE_SWARM_TEMP

            if high_risk:
                avd_str = ", ".join(
                    str(s.get("stand_number", "?")) for s in high_risk[:5]
                )
                alerts.append({
                    "severity": SEVERITY_CRITICAL,
                    "category": CATEGORY_BARK_BEETLE,
                    "title": "Hög barkborrerisk – Aktiv säsong",
                    "message": (
                        f"Avdelning {avd_str} har förhöjd barkborrerisk. "
                        f"{'Temperaturer gynnar svärmning – inspektera snarast!' if warm_enough else 'Bevaka bestånden regelbundet.'}"
                    ),
                    "affected_stands": [s.get("stand_number") for s in high_risk[:5]],
                    "data": {
                        "high_risk_count": len(high_risk),
                        "warm_enough_for_swarming": warm_enough,
                    },
                    "action": (
                        "Inspektera granbestånd efter borrangrepp. "
                        "Prioritera uttag av angripna träd. "
                        "Avverka och forsla bort virke skyndsamt."
                    ),
                })
            elif susceptible and warm_enough:
                alerts.append({
                    "severity": SEVERITY_WARNING,
                    "category": CATEGORY_BARK_BEETLE,
                    "title": "Barkborresäsong – Gynnsam temperatur",
                    "message": (
                        f"Temperaturen gynnar barkborresvärmning (>18°C). "
                        f"{len(susceptible)} granavdelningar med hög ålder bör bevakas."
                    ),
                    "affected_stands": [s.get("stand_number") for s in susceptible[:5]],
                    "data": {"susceptible_count": len(susceptible)},
                    "action": "Bevaka äldre granbestånd. Leta efter borrspån vid stambasen.",
                })
        else:
            # Off-season info
            if high_risk:
                alerts.append({
                    "severity": SEVERITY_INFO,
                    "category": CATEGORY_BARK_BEETLE,
                    "title": "Barkborrerisk – Planera åtgärder",
                    "message": (
                        f"{len(high_risk)} avdelningar har förhöjd barkborrerisk. "
                        "Planera förebyggande åtgärder inför kommande säsong."
                    ),
                    "affected_stands": [s.get("stand_number") for s in high_risk[:5]],
                    "data": {"high_risk_count": len(high_risk)},
                    "action": "Planera uttag av riskbestånd under vinter/vår.",
                })

        return alerts

    # ── Harvesting alerts ─────────────────────────────────────────

    def _harvesting_alerts(self, stands: list[dict]) -> list[dict]:
        """Generate alerts for stands that need or are ready for harvesting."""
        alerts = []

        overdue = []
        ready = []

        for s in stands:
            age = s.get("age_years")
            si = s.get("site_index")
            pine = s.get("pine_pct", 0) or 0
            spruce = s.get("spruce_pct", 0) or 0
            tc = s.get("target_class", "PG") or "PG"

            if age is None or si is None or si <= 0:
                continue
            if tc in ("NS", "NO"):
                continue  # Nature conservation - no harvesting

            # Get lowest harvesting age
            table = PINE_HARVEST_AGE if pine >= spruce else SPRUCE_HARVEST_AGE
            si_rounded = round(si / 2) * 2
            closest_si = min(table.keys(), key=lambda x: abs(x - si_rounded))
            harvest_age = table[closest_si]

            if age >= harvest_age * 1.5:
                overdue.append(s)
            elif age >= harvest_age:
                ready.append(s)

        if overdue:
            avd_str = ", ".join(
                str(s.get("stand_number", "?")) for s in overdue[:5]
            )
            total_vol = sum(s.get("total_volume_m3", 0) or 0 for s in overdue)
            alerts.append({
                "severity": SEVERITY_WARNING,
                "category": CATEGORY_HARVESTING,
                "title": "Överåldrig skog – Slutavverkning angelägen",
                "message": (
                    f"Avdelning {avd_str} har passerat lägsta slutavverkningsålder "
                    f"med god marginal. Totalt {total_vol:.0f} m³sk virkesförråd. "
                    "Risk för kvalitetsförsämring och stormkänslighet ökar."
                ),
                "affected_stands": [s.get("stand_number") for s in overdue[:5]],
                "data": {"overdue_count": len(overdue), "total_volume": total_vol},
                "action": "Planera föryngringsavverkning. Kontakta virkesköpare.",
            })

        if ready and not overdue:
            alerts.append({
                "severity": SEVERITY_INFO,
                "category": CATEGORY_HARVESTING,
                "title": f"{len(ready)} avdelningar är avverkningsmogna",
                "message": (
                    f"{len(ready)} avdelningar har uppnått lägsta slutavverkningsålder. "
                    "Överväg avverkning efter marknadsprisutveckling."
                ),
                "affected_stands": [s.get("stand_number") for s in ready[:5]],
                "data": {"ready_count": len(ready)},
                "action": None,
            })

        return alerts

    # ── Thinning alerts ───────────────────────────────────────────

    def _thinning_alerts(self, stands: list[dict]) -> list[dict]:
        """Generate alerts for stands that need thinning."""
        alerts = []
        needs_thinning = []

        for s in stands:
            ba = s.get("basal_area_m2", 0) or 0
            age = s.get("age_years", 0) or 0
            si = s.get("site_index", 0) or 0
            tc = s.get("target_class", "PG") or "PG"
            height = s.get("mean_height_m", 0) or 0

            if tc in ("NO",):
                continue

            # High basal area relative to site quality = needs thinning
            # Rule of thumb: BA > 28 m²/ha for most stands signals thinning need
            if ba >= 30 and 20 <= age <= 70 and height >= 10:
                needs_thinning.append(s)
            elif ba >= 26 and 25 <= age <= 50 and si >= 24:
                needs_thinning.append(s)

        if needs_thinning:
            avd_str = ", ".join(
                str(s.get("stand_number", "?")) for s in needs_thinning[:5]
            )
            alerts.append({
                "severity": SEVERITY_INFO,
                "category": CATEGORY_THINNING,
                "title": f"Gallringsbehov i {len(needs_thinning)} avdelningar",
                "message": (
                    f"Avdelning {avd_str} har hög grundyta och gynnas av gallring. "
                    "Gallring förbättrar tillväxten och minskar risken för stormfällning."
                ),
                "affected_stands": [s.get("stand_number") for s in needs_thinning[:5]],
                "data": {"count": len(needs_thinning)},
                "action": "Planera gallring. Vintergallring ger mindre körskador.",
            })

        return alerts

    # ── Regeneration alerts ───────────────────────────────────────

    def _regeneration_alerts(self, stands: list[dict]) -> list[dict]:
        """Generate alerts for clearcut areas needing regeneration."""
        alerts = []
        needs_regen = []

        for s in stands:
            vol = s.get("volume_m3_per_ha", 0) or 0
            age = s.get("age_years", 0) or 0
            action = s.get("proposed_action", "")

            # Very low volume + young = probably clearcut, needs regeneration
            if vol < 10 and age <= 3 and action in ("foryngring", ""):
                needs_regen.append(s)

        if needs_regen:
            avd_str = ", ".join(
                str(s.get("stand_number", "?")) for s in needs_regen[:5]
            )
            alerts.append({
                "severity": SEVERITY_WARNING,
                "category": CATEGORY_REGENERATION,
                "title": "Föryngringsskyldighet",
                "message": (
                    f"Avdelning {avd_str} är kalmark. Enligt Skogsvårdslagen ska "
                    "ny skog anläggas senast 3 år efter avverkning."
                ),
                "affected_stands": [s.get("stand_number") for s in needs_regen],
                "data": {"count": len(needs_regen)},
                "action": "Planera plantering eller markberedning.",
            })

        return alerts

    # ── Growth alerts ─────────────────────────────────────────────

    def _growth_alerts(
        self, stands: list[dict], property_data: Optional[dict] = None
    ) -> list[dict]:
        """Growth and productivity insights."""
        alerts = []

        if not stands:
            return alerts

        # Calculate total volume and area
        total_vol = sum(s.get("total_volume_m3", 0) or 0 for s in stands)
        total_area = sum(s.get("area_ha", 0) or 0 for s in stands)
        mean_vol_ha = total_vol / total_area if total_area > 0 else 0

        # High-volume property
        if mean_vol_ha >= 200:
            alerts.append({
                "severity": SEVERITY_SUCCESS,
                "category": CATEGORY_GROWTH,
                "title": "Högt virkesförråd",
                "message": (
                    f"Medelförrådet är {mean_vol_ha:.0f} m³sk/ha, "
                    "vilket är över riksgenomsnittet (~140 m³sk/ha). "
                    "God skoglig tillväxt och produktivitet."
                ),
                "affected_stands": [],
                "data": {"mean_vol_ha": mean_vol_ha, "total_vol": total_vol},
                "action": None,
            })

        # Low-volume stands that may need attention
        low_vol_old = [
            s for s in stands
            if (s.get("volume_m3_per_ha", 0) or 0) < 80
            and (s.get("age_years", 0) or 0) >= 40
            and (s.get("target_class", "PG") or "PG") not in ("NO",)
        ]
        if low_vol_old:
            alerts.append({
                "severity": SEVERITY_INFO,
                "category": CATEGORY_GROWTH,
                "title": f"{len(low_vol_old)} avdelningar med låg volym",
                "message": (
                    "Dessa avdelningar har lägre volym än förväntat för sin ålder. "
                    "Kan bero på låg bonitet, tidigare skador eller bristfällig föryngring."
                ),
                "affected_stands": [s.get("stand_number") for s in low_vol_old[:5]],
                "data": {"count": len(low_vol_old)},
                "action": "Utvärdera orsak. Överväg röjning eller kompletteringsplantering.",
            })

        return alerts

    # ── Certification alerts ──────────────────────────────────────

    def _certification_alerts(
        self, stands: list[dict], property_data: Optional[dict] = None
    ) -> list[dict]:
        """Certification compliance alerts."""
        alerts = []

        if not stands:
            return alerts

        total_area = sum(s.get("area_ha", 0) or 0 for s in stands)
        if total_area == 0:
            return alerts

        ns_no_area = sum(
            (s.get("area_ha", 0) or 0)
            for s in stands
            if (s.get("target_class", "") or "") in ("NS", "NO")
        )
        conservation_pct = (ns_no_area / total_area) * 100

        # FSC/PEFC requires at least 5% conservation
        if conservation_pct < 5.0:
            alerts.append({
                "severity": SEVERITY_WARNING,
                "category": CATEGORY_CERTIFICATION,
                "title": "Certifieringskrav – Naturvårdsandel under 5%",
                "message": (
                    f"Nuvarande naturvårdsandel (NS + NO) är {conservation_pct:.1f}% "
                    f"av produktiv areal. FSC/PEFC kräver minst 5%. "
                    f"Ytterligare {(5.0 - conservation_pct) * total_area / 100:.1f} ha "
                    "bör avsättas för naturvård."
                ),
                "affected_stands": [],
                "data": {
                    "conservation_pct": conservation_pct,
                    "ns_no_area": ns_no_area,
                    "needed_ha": (5.0 - conservation_pct) * total_area / 100,
                },
                "action": "Identifiera lämpliga avdelningar att omklassa till NS/NO.",
            })
        elif conservation_pct >= 5.0:
            alerts.append({
                "severity": SEVERITY_SUCCESS,
                "category": CATEGORY_CERTIFICATION,
                "title": "Naturvårdskrav uppfyllt",
                "message": (
                    f"Naturvårdsandelen (NS + NO) är {conservation_pct:.1f}% "
                    "– uppfyller certifieringskraven."
                ),
                "affected_stands": [],
                "data": {"conservation_pct": conservation_pct},
                "action": None,
            })

        # Contorta check
        contorta_area = sum(
            (s.get("area_ha", 0) or 0) * ((s.get("contorta_pct", 0) or 0) / 100)
            for s in stands
        )
        contorta_pct = (contorta_area / total_area) * 100 if total_area > 0 else 0

        if contorta_pct > 15:
            alerts.append({
                "severity": SEVERITY_WARNING,
                "category": CATEGORY_CERTIFICATION,
                "title": "Contortaandel närmar sig gränsvärdet",
                "message": (
                    f"Contorta utgör {contorta_pct:.1f}% av arealen. "
                    "FSC tillåter max 20%. Planera successiv omvandling."
                ),
                "affected_stands": [],
                "data": {"contorta_pct": contorta_pct},
                "action": "Omvandla contortabestånd till inhemska trädslag vid föryngring.",
            })

        return alerts

    # ── Seasonal alerts ───────────────────────────────────────────

    def _seasonal_alerts(self, stands: list[dict]) -> list[dict]:
        """Context-sensitive seasonal recommendations."""
        alerts = []
        month = date.today().month

        # Find stands needing pre-commercial thinning (röjning)
        needs_clearing = [
            s for s in stands
            if (s.get("mean_height_m", 0) or 0) >= 1.5
            and (s.get("mean_height_m", 0) or 0) <= 5.0
            and (s.get("age_years", 0) or 0) <= 25
        ]

        if month in (6, 7, 8):
            # Summer: röjning season
            if needs_clearing:
                alerts.append({
                    "severity": SEVERITY_INFO,
                    "category": CATEGORY_SEASONAL,
                    "title": "Röjningssäsong",
                    "message": (
                        f"Sommaren är bästa tid för röjning. "
                        f"{len(needs_clearing)} avdelningar kan behöva röjning."
                    ),
                    "affected_stands": [s.get("stand_number") for s in needs_clearing[:5]],
                    "data": {"count": len(needs_clearing)},
                    "action": "Planera röjning i juni-augusti för bäst effekt.",
                })
        elif month in (11, 12, 1, 2):
            # Winter: good for logging (frozen ground)
            harvest_candidates = [
                s for s in stands
                if (s.get("proposed_action", "") in ("slutavverkning", "gallring"))
                and (s.get("action_urgency", 5) or 5) <= 3
            ]
            if harvest_candidates:
                alerts.append({
                    "severity": SEVERITY_INFO,
                    "category": CATEGORY_SEASONAL,
                    "title": "Vinteravverkning – Tjälperiod",
                    "message": (
                        "Frusen mark ger bästa förutsättningar för avverkning "
                        "med minimal markpåverkan. "
                        f"{len(harvest_candidates)} avdelningar har planerade åtgärder."
                    ),
                    "affected_stands": [
                        s.get("stand_number") for s in harvest_candidates[:5]
                    ],
                    "data": {"count": len(harvest_candidates)},
                    "action": "Kontakta avverkningsentreprenör för vinteruppdrag.",
                })
        elif month in (3, 4, 5):
            # Spring: planting season
            kalmark = [
                s for s in stands
                if (s.get("volume_m3_per_ha", 0) or 0) < 10
                and (s.get("age_years", 0) or 0) <= 3
            ]
            if kalmark:
                alerts.append({
                    "severity": SEVERITY_INFO,
                    "category": CATEGORY_SEASONAL,
                    "title": "Planteringssäsong",
                    "message": (
                        f"Våren är optimal för plantering. "
                        f"{len(kalmark)} avdelningar är kalmark."
                    ),
                    "affected_stands": [s.get("stand_number") for s in kalmark],
                    "data": {"count": len(kalmark)},
                    "action": "Beställ plantor och planera plantering i april-juni.",
                })

        return alerts
