def calculate_loss(input_kg: float, output_kg: float) -> dict:
    loss_kg = max(input_kg - output_kg, 0.0)
    loss_pct = (loss_kg / input_kg) * 100.0 if input_kg > 0 else 0.0
    return {"loss_kg": round(loss_kg, 2), "loss_pct": round(loss_pct, 2)}
