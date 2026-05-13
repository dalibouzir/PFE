from app.ai.tools.material_balance_tools import compute_material_balance


def test_material_balance_calculates_loss_and_efficiency():
    result = compute_material_balance(
        input_quantity=100,
        output_quantity=80,
        stage_breakdown=[],
    )

    assert result["total_loss_quantity"] == 20
    assert result["loss_percentage"] == 20
    assert result["efficiency_percentage"] == 80
    assert result["warnings"] == []


def test_material_balance_rejects_non_positive_input_quantity():
    result = compute_material_balance(input_quantity=0, output_quantity=80, stage_breakdown=[])

    assert "La quantité d’entrée doit être supérieure à 0." in result["warnings"]
    assert result["loss_percentage"] == 0
    assert result["efficiency_percentage"] == 0


def test_material_balance_handles_negative_output_quantity():
    result = compute_material_balance(input_quantity=100, output_quantity=-5, stage_breakdown=[])

    assert "La quantité de sortie ne peut pas être négative." in result["warnings"]
    assert result["output_quantity"] == 0
    assert result["loss_percentage"] == 100


def test_material_balance_warns_when_output_exceeds_input():
    result = compute_material_balance(input_quantity=100, output_quantity=120, stage_breakdown=[])

    assert "La quantité de sortie est supérieure à la quantité d’entrée." in result["warnings"]
    assert result["loss_percentage"] == -20
    assert result["efficiency_percentage"] == 120


def test_material_balance_warns_on_incomplete_stage_breakdown():
    result = compute_material_balance(input_quantity=100, output_quantity=90, stage_breakdown=None)

    assert "Le détail par étape est incomplet." in result["warnings"]
