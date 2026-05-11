from app.ml.features.engineer import build_features


def test_feature_engineering_builds_features(db_session):
    feature_set = build_features(db_session)
    assert not feature_set.features.empty
    expected_columns = {
        "product",
        "process_type",
        "stage_canonical",
        "product_stage_key",
        "qty_in",
        "qty_in_log",
        "qty_out",
        "batch_size",
        "batch_size_log",
        "stock_level",
        "stock_pressure_ratio",
        "date",
        "month",
        "week_of_year",
        "season",
        "stage_order",
        "is_drying_stage",
        "is_sorting_stage",
        "is_packaging_stage",
        "historical_avg_loss_same_product",
        "historical_avg_loss_same_stage",
        "historical_avg_efficiency_same_stage",
        "product_stage_historical_avg_loss",
        "product_stage_historical_median_loss",
        "product_stage_rolling_loss_last_5",
        "product_stage_rolling_loss_last_10",
        "stage_season_avg_loss",
        "product_stage_season_avg_loss",
        "loss_volatility_product_stage",
        "deviation_from_stage_avg",
        "previous_batch_loss",
        "days_since_previous_batch",
        "rolling_loss_last_n_batches",
        "rolling_efficiency_last_n_batches",
        "loss_pct",
        "efficiency_pct",
    }
    assert expected_columns.issubset(set(feature_set.features.columns))
