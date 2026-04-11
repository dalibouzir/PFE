def process_efficiency(output_kg: float, expected_output_kg: float) -> float:
    if expected_output_kg <= 0:
        return 0.0
    return round((output_kg / expected_output_kg) * 100.0, 2)
