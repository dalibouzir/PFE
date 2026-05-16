def generate_recommendation(loss_pct: float, drying_hours: float) -> list[str]:
    recommendations: list[str] = []

    if loss_pct > 20:
        recommendations.append(
            "High post-harvest loss detected. Improve mango sorting before slicing and drying."
        )
    if drying_hours > 18:
        recommendations.append(
            "Drying duration is high. Monitor tray humidity and rotate trays every 2 hours."
        )
    if not recommendations:
        recommendations.append("Process indicators are stable. Keep weekly monitoring active.")

    return recommendations
