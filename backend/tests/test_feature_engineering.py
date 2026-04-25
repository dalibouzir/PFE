from app.ml.features.engineer import build_features


def test_feature_engineering_builds_features(db_session):
    feature_set = build_features(db_session)
    assert not feature_set.features.empty
    expected_columns = {
        "product",
        "process_type",
        "qty_in",
        "qty_out",
        "batch_size",
        "stock_level",
        "date",
        "month",
        "week_of_year",
        "season",
        "historical_avg_loss_same_product",
        "historical_avg_loss_same_stage",
        "historical_avg_efficiency_same_stage",
        "deviation_from_stage_avg",
        "previous_batch_loss",
        "rolling_loss_last_n_batches",
        "rolling_efficiency_last_n_batches",
        "loss_pct",
        "efficiency_pct",
    }
    assert expected_columns.issubset(set(feature_set.features.columns))
