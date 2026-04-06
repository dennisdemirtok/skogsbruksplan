import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# Swedish timber prices (approximate 2024 prices in SEK/m3fub)
TIMBER_PRICES = {
    "pine_timber": 650,       # Tall timmer
    "spruce_timber": 600,     # Gran timmer
    "pine_pulpwood": 350,     # Tall massaved
    "spruce_pulpwood": 320,   # Gran massaved
    "birch_pulpwood": 300,    # Björk massaved
    "deciduous_timber": 400,  # Löv timmer (generellt)
    "contorta_pulpwood": 310, # Contorta massaved
}

# Discount rate for NPV calculations
DISCOUNT_RATE = 0.025  # 2.5%


class EconomicCalculator:
    def calculate_stand_economics(self, stand_data: dict) -> dict:
        volume_per_ha = stand_data.get("volume_m3_per_ha")
        area_ha = stand_data.get("area_ha")
        mean_diameter = stand_data.get("mean_diameter_cm")
        pine_pct = (stand_data.get("pine_pct") or 0) / 100.0
        spruce_pct = (stand_data.get("spruce_pct") or 0) / 100.0
        deciduous_pct = (stand_data.get("deciduous_pct") or 0) / 100.0
        contorta_pct = (stand_data.get("contorta_pct") or 0) / 100.0

        if volume_per_ha is None or area_ha is None or area_ha <= 0:
            return {
                "timber_volume_m3": 0,
                "pulpwood_volume_m3": 0,
                "gross_value_sek": 0,
                "harvesting_cost_sek": 0,
                "net_value_sek": 0,
                "npv_10yr": 0,
            }

        total_volume = volume_per_ha * area_ha

        # Convert standing volume (m3sk) to merchantable volume (m3fub)
        # Approximation: m3fub is roughly 83% of m3sk
        fub_factor = 0.83
        total_volume_fub = total_volume * fub_factor

        # Estimate timber vs pulpwood ratio based on mean diameter
        timber_ratio = self._estimate_timber_ratio(mean_diameter)
        pulpwood_ratio = 1.0 - timber_ratio

        # Volume by species
        pine_volume = total_volume_fub * pine_pct
        spruce_volume = total_volume_fub * spruce_pct
        deciduous_volume = total_volume_fub * deciduous_pct
        contorta_volume = total_volume_fub * contorta_pct

        # Timber volumes
        pine_timber = pine_volume * timber_ratio
        spruce_timber = spruce_volume * timber_ratio
        deciduous_timber = deciduous_volume * timber_ratio * 0.5  # Less timber from deciduous
        contorta_timber = 0  # Contorta rarely makes timber

        total_timber = pine_timber + spruce_timber + deciduous_timber + contorta_timber

        # Pulpwood volumes
        pine_pulp = pine_volume * pulpwood_ratio
        spruce_pulp = spruce_volume * pulpwood_ratio
        deciduous_pulp = deciduous_volume * (1 - timber_ratio * 0.5)
        contorta_pulp = contorta_volume

        total_pulpwood = pine_pulp + spruce_pulp + deciduous_pulp + contorta_pulp

        # Gross value calculation
        gross_value = (
            pine_timber * TIMBER_PRICES["pine_timber"]
            + spruce_timber * TIMBER_PRICES["spruce_timber"]
            + deciduous_timber * TIMBER_PRICES["deciduous_timber"]
            + pine_pulp * TIMBER_PRICES["pine_pulpwood"]
            + spruce_pulp * TIMBER_PRICES["spruce_pulpwood"]
            + deciduous_pulp * TIMBER_PRICES["birch_pulpwood"]
            + contorta_pulp * TIMBER_PRICES["contorta_pulpwood"]
        )

        # Harvesting cost calculation
        harvesting_cost = self._calculate_harvesting_cost(
            total_volume_fub, volume_per_ha * fub_factor, area_ha
        )

        # Net value
        net_value = gross_value - harvesting_cost

        # NPV over 10 years (assuming the stand is harvested now)
        npv_10yr = self._calculate_npv(net_value, years=10)

        return {
            "timber_volume_m3": round(total_timber, 1),
            "pulpwood_volume_m3": round(total_pulpwood, 1),
            "gross_value_sek": round(gross_value, 0),
            "harvesting_cost_sek": round(harvesting_cost, 0),
            "net_value_sek": round(net_value, 0),
            "npv_10yr": round(npv_10yr, 0),
        }

    def _estimate_timber_ratio(self, mean_diameter: Optional[float]) -> float:
        if mean_diameter is None:
            return 0.40  # Default estimate

        if mean_diameter < 14:
            return 0.0   # Too small for timber, all pulpwood
        elif mean_diameter < 16:
            return 0.10
        elif mean_diameter < 18:
            return 0.20
        elif mean_diameter < 20:
            return 0.30
        elif mean_diameter < 22:
            return 0.40
        elif mean_diameter < 24:
            return 0.50
        elif mean_diameter < 26:
            return 0.55
        elif mean_diameter < 28:
            return 0.60
        elif mean_diameter < 30:
            return 0.65
        elif mean_diameter < 35:
            return 0.70
        else:
            return 0.75  # Very large trees, high timber ratio

    def _calculate_harvesting_cost(
        self, total_volume_fub: float, volume_per_ha_fub: float, area_ha: float
    ) -> float:
        if total_volume_fub <= 0:
            return 0

        # Base cost per m3fub: ~120-180 kr depending on conditions
        # Factors: volume/ha (higher = cheaper), terrain, tree size

        if volume_per_ha_fub > 200:
            base_cost = 120  # High volume, efficient harvesting
        elif volume_per_ha_fub > 150:
            base_cost = 135
        elif volume_per_ha_fub > 100:
            base_cost = 150
        elif volume_per_ha_fub > 50:
            base_cost = 165
        else:
            base_cost = 180  # Low volume, expensive per m3

        # Small areas have proportionally higher fixed costs
        if area_ha < 1.0:
            base_cost *= 1.15
        elif area_ha < 2.0:
            base_cost *= 1.08
        elif area_ha < 5.0:
            base_cost *= 1.03

        return total_volume_fub * base_cost

    def _calculate_npv(self, net_value: float, years: int = 10) -> float:
        if net_value <= 0:
            return net_value

        # Present value of a single future cash flow
        # Assuming immediate harvest, the NPV is the net value discounted
        # If we plan to harvest in the future, discount by years
        # For "harvest now" scenario, NPV = net_value (no discounting needed)
        # For a 10-year planning horizon, we show what the stand value is worth
        # if harvested at the optimal time

        # Simple approach: if harvested now, NPV = net_value
        # We also calculate what the stand would be worth if left to grow
        # Typical Swedish forest growth rate: ~3-5 m3sk/ha/year
        # We use a simplified model here

        npv = net_value / math.pow(1 + DISCOUNT_RATE, 0)  # Harvest now = no discount
        return npv
