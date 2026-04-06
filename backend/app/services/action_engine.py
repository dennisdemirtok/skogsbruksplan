import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Swedish forestry site index tables (SI H100 system)
# Lowest harvesting age (lägsta slutavverkningsålder) by site index
# Based on Skogsstyrelsen regulations (SKSFS 2011:7)

# Pine (Tall) - Lowest harvesting age by SI
PINE_LOWEST_HARVESTING_AGE = {
    # SI H100: min age
    32: 45,
    30: 50,
    28: 55,
    26: 55,
    24: 60,
    22: 65,
    20: 70,
    18: 80,
    16: 90,
    14: 100,
    12: 110,
}

# Spruce (Gran) - Lowest harvesting age by SI
SPRUCE_LOWEST_HARVESTING_AGE = {
    # SI H100: min age
    36: 40,
    34: 45,
    32: 45,
    30: 50,
    28: 50,
    26: 55,
    24: 60,
    22: 65,
    20: 70,
    18: 75,
    16: 85,
    14: 95,
}

# Gallring (thinning) basal area thresholds (m2/ha)
# Based on typical Swedish forestry guidelines by SI and age class
# Format: {si_class: {age_range: threshold_basal_area}}
THINNING_BASAL_AREA_THRESHOLDS = {
    "high": {  # SI >= 26
        "young": 22,    # age 25-40
        "middle": 26,   # age 40-60
        "mature": 28,   # age 60+
    },
    "medium": {  # SI 18-25
        "young": 20,
        "middle": 24,
        "mature": 26,
    },
    "low": {  # SI < 18
        "young": 18,
        "middle": 22,
        "mature": 24,
    },
}


class ActionEngine:
    def propose_action(self, stand_data: dict) -> dict:
        age = stand_data.get("age_years")
        site_index = stand_data.get("site_index")
        volume = stand_data.get("volume_m3_per_ha")
        basal_area = stand_data.get("basal_area_m2")
        mean_height = stand_data.get("mean_height_m")
        pine_pct = stand_data.get("pine_pct", 0) or 0
        spruce_pct = stand_data.get("spruce_pct", 0) or 0
        deciduous_pct = stand_data.get("deciduous_pct", 0) or 0
        target_class = stand_data.get("target_class", "PG")
        bark_beetle_risk = stand_data.get("bark_beetle_risk", 0) or 0

        if target_class == "NO":
            return {
                "action": "ingen",
                "urgency": 5,
                "reasoning": "Avdelningen har målklass NO (naturvård orörd) och ska lämnas utan åtgärd.",
            }

        if target_class == "NS":
            return self._ns_action(stand_data)

        if target_class == "PF":
            return {
                "action": "ingen",
                "urgency": 5,
                "reasoning": "Avdelningen har målklass PF (produktion med förstärkt hänsyn). "
                             "Eventuella åtgärder bör planeras med extra naturhänsyn.",
            }

        if age is None or site_index is None:
            return {
                "action": "ingen",
                "urgency": 5,
                "reasoning": "Otillräckliga data för att föreslå åtgärd. "
                             "Ålder och/eller bonitet saknas.",
            }

        if bark_beetle_risk > 0.6 and spruce_pct > 60:
            return self._bark_beetle_action(stand_data)

        if age < 20 and mean_height is not None and 1.0 <= mean_height <= 4.0:
            return {
                "action": "rojning",
                "urgency": self._rojning_urgency(age, mean_height),
                "reasoning": f"Ungskogsröjning rekommenderas. Beståndet är {age} år med "
                             f"medelhöjd {mean_height} m. Röjning bör utföras för att "
                             f"säkerställa god stamtillväxt och kvalitetsutveckling.",
            }

        lowest_age = self._get_lowest_harvesting_age(
            site_index, pine_pct, spruce_pct
        )
        if lowest_age is not None and age >= lowest_age and volume is not None and volume > 150:
            urgency = self._slutavverkning_urgency(
                age, lowest_age, volume, bark_beetle_risk
            )
            return {
                "action": "slutavverkning",
                "urgency": urgency,
                "reasoning": f"Beståndet har uppnått lägsta slutavverkningsålder ({lowest_age} år, "
                             f"aktuell ålder {age} år) med volym {volume} m3sk/ha. "
                             f"SI={site_index}. Slutavverkning rekommenderas.",
            }

        if self._should_thin(age, site_index, basal_area, pine_pct, spruce_pct):
            urgency = self._gallring_urgency(basal_area, site_index, age)
            return {
                "action": "gallring",
                "urgency": urgency,
                "reasoning": f"Gallring rekommenderas. Beståndet är {age} år med "
                             f"grundyta {basal_area} m2/ha och SI={site_index}. "
                             f"Gallring behövs för att upprätthålla god tillväxt.",
            }

        if age is not None and age < 5 and (volume is None or volume < 10):
            return {
                "action": "foryngring",
                "urgency": 3,
                "reasoning": "Beståndet är i föryngringsfas. Kontrollera att föryngring "
                             "är etablerad och eventuellt kompletteringsplantera.",
            }

        return {
            "action": "ingen",
            "urgency": 5,
            "reasoning": f"Ingen åtgärd föreslås för närvarande. Beståndet är {age} år, "
                         f"SI={site_index}, volym={volume} m3sk/ha.",
        }

    def classify_target_class(
        self, stand_data: dict, nature_values: Optional[dict] = None
    ) -> str:
        if nature_values is None:
            nature_values = {}

        is_key_biotope = nature_values.get("key_biotope", False)
        has_red_listed = bool(nature_values.get("red_listed_species"))
        dead_wood_m3 = nature_values.get("dead_wood_m3", 0) or 0
        old_trees = nature_values.get("old_trees", False)
        high_nature_value = nature_values.get("high_nature_value", False)

        if is_key_biotope:
            return "NO"

        if has_red_listed and (dead_wood_m3 > 10 or old_trees):
            return "NS"

        if high_nature_value or dead_wood_m3 > 5:
            return "PF"

        age = stand_data.get("age_years", 0) or 0
        site_index = stand_data.get("site_index", 20) or 20
        lowest_age = self._get_lowest_harvesting_age(
            site_index,
            stand_data.get("pine_pct", 0) or 0,
            stand_data.get("spruce_pct", 0) or 0,
        )

        if lowest_age and age > lowest_age * 1.5:
            return "PF"

        return "PG"

    def _ns_action(self, stand_data: dict) -> dict:
        age = stand_data.get("age_years", 0) or 0
        spruce_pct = stand_data.get("spruce_pct", 0) or 0
        deciduous_pct = stand_data.get("deciduous_pct", 0) or 0

        if spruce_pct > 80 and age < 60:
            return {
                "action": "gallring",
                "urgency": 4,
                "reasoning": "Målklass NS. Gallring för att gynna lövträd och öka "
                             "biologisk mångfald. Avverka gran för att gynna löv och "
                             "skapa mer varierad beståndsstruktur.",
            }

        return {
            "action": "ingen",
            "urgency": 5,
            "reasoning": "Målklass NS (naturvård, skötsel). Beståndet kräver för "
                         "närvarande inga aktiva naturvårdsåtgärder.",
        }

    def _bark_beetle_action(self, stand_data: dict) -> dict:
        age = stand_data.get("age_years", 0) or 0
        volume = stand_data.get("volume_m3_per_ha", 0) or 0
        bark_beetle_risk = stand_data.get("bark_beetle_risk", 0) or 0
        site_index = stand_data.get("site_index")

        lowest_age = self._get_lowest_harvesting_age(
            site_index or 20,
            stand_data.get("pine_pct", 0) or 0,
            stand_data.get("spruce_pct", 0) or 0,
        )

        if lowest_age and age >= lowest_age and volume > 100:
            return {
                "action": "slutavverkning",
                "urgency": 1,
                "reasoning": f"HÖG GRANBARKBORRISK ({bark_beetle_risk:.0%})! "
                             f"Grandominerat bestånd ({stand_data.get('spruce_pct', 0)}% gran) "
                             f"med hög risk för barkborreangrepp. Beståndet har nått "
                             f"avverkningsbar ålder. Brådskande slutavverkning rekommenderas.",
            }

        if age >= 30:
            return {
                "action": "gallring",
                "urgency": 1,
                "reasoning": f"HÖG GRANBARKBORRISK ({bark_beetle_risk:.0%})! "
                             f"Grandominerat bestånd ({stand_data.get('spruce_pct', 0)}% gran). "
                             f"Brådskande gallring för att minska trängsel och risk. "
                             f"Prioritera uttag av försvagade granar.",
            }

        return {
            "action": "ingen",
            "urgency": 2,
            "reasoning": f"HÖG GRANBARKBORRISK ({bark_beetle_risk:.0%})! "
                         f"Beståndet är dock för ungt för avverkning. "
                         f"Övervaka noggrant och avlägsna angripna träd.",
        }

    def _get_lowest_harvesting_age(
        self, site_index: float, pine_pct: float, spruce_pct: float
    ) -> Optional[int]:
        si_rounded = round(site_index / 2) * 2

        if pine_pct >= spruce_pct:
            age_table = PINE_LOWEST_HARVESTING_AGE
        else:
            age_table = SPRUCE_LOWEST_HARVESTING_AGE

        if si_rounded in age_table:
            return age_table[si_rounded]

        closest_si = min(age_table.keys(), key=lambda x: abs(x - si_rounded))
        return age_table[closest_si]

    def _should_thin(
        self,
        age: Optional[int],
        site_index: Optional[float],
        basal_area: Optional[float],
        pine_pct: float,
        spruce_pct: float,
    ) -> bool:
        if age is None or site_index is None or basal_area is None:
            return False

        lowest_age = self._get_lowest_harvesting_age(site_index, pine_pct, spruce_pct)
        if lowest_age is None:
            return False

        if age < 25 or age >= lowest_age:
            return False

        if site_index >= 26:
            si_class = "high"
        elif site_index >= 18:
            si_class = "medium"
        else:
            si_class = "low"

        thresholds = THINNING_BASAL_AREA_THRESHOLDS[si_class]

        if age <= 40:
            threshold = thresholds["young"]
        elif age <= 60:
            threshold = thresholds["middle"]
        else:
            threshold = thresholds["mature"]

        return basal_area >= threshold

    def _rojning_urgency(self, age: int, mean_height: float) -> int:
        if mean_height >= 3.0:
            return 1
        if mean_height >= 2.0:
            return 2
        if age >= 10:
            return 2
        return 3

    def _slutavverkning_urgency(
        self, age: int, lowest_age: int, volume: float, bark_beetle_risk: float
    ) -> int:
        if bark_beetle_risk > 0.4:
            return 1
        over_age_ratio = age / lowest_age if lowest_age > 0 else 1
        if over_age_ratio > 1.3 and volume > 250:
            return 1
        if over_age_ratio > 1.2 or volume > 300:
            return 2
        if over_age_ratio > 1.0:
            return 3
        return 4

    def _gallring_urgency(
        self, basal_area: Optional[float], site_index: Optional[float], age: Optional[int]
    ) -> int:
        if basal_area is None or site_index is None:
            return 3
        if basal_area > 35:
            return 1
        if basal_area > 30:
            return 2
        return 3
