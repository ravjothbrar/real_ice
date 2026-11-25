"""Real Ice scale check (brief 5.8). Source for targets: Ocean Visions Arctic ice thickening roadmap page."""
TARGET_KM2 = 1_000_000          # km2 per year
ENERGY_MWH_PER_KM2 = 8.0        # MWh per km2
ICE_SAFE_WINDOW_DAYS = 90       # January - March (ARIA community-engagement PDF, winter 2025/26)


def scale(area_km2, throughput_km2_per_drone_day, window_days=ICE_SAFE_WINDOW_DAYS,
          mwh_per_km2=ENERGY_MWH_PER_KM2):
    fleet = area_km2 / (throughput_km2_per_drone_day * window_days)
    return {
        "area_km2": area_km2,
        "share_of_target": area_km2 / TARGET_KM2,
        "energy_twh": area_km2 * mwh_per_km2 / 1e6,
        "fleet": fleet,
        "assumption": {"throughput_km2_per_drone_day": throughput_km2_per_drone_day, "window_days": window_days},
        "fleet_label": f"ASSUMPTION: {throughput_km2_per_drone_day} km2 per drone per day over {window_days} days",
    }
