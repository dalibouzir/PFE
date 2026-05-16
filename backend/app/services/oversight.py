from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.cooperative import Cooperative
from app.models.institution import Institution
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.recommendation import Recommendation
from app.models.stock import Stock
from app.models.user import User
from app.schemas.oversight import CooperativeOversightResponse, CooperativeOversightRow, OversightSummary
from app.services.helpers import COOPERATIVE_ROLES, round_metric


def _loss_efficiency(initial_qty: float, current_qty: float) -> tuple[float, float]:
    if initial_qty <= 0:
        return 0.0, 0.0
    loss_rate = ((initial_qty - current_qty) / initial_qty) * 100.0
    efficiency_rate = (current_qty / initial_qty) * 100.0
    return round_metric(loss_rate), round_metric(efficiency_rate)


def _cooperative_rows(db: Session, cooperative_ids: list):
    if not cooperative_ids:
        return []

    user_agg = {
        row.cooperative_id: row
        for row in db.execute(
            select(
                User.cooperative_id,
                func.count(User.id).label("users_count"),
                func.sum(case((User.role == "manager", 1), else_=0)).label("managers_count"),
                func.sum(case((User.role == "viewer", 1), else_=0)).label("viewers_count"),
            )
            .where(User.cooperative_id.in_(cooperative_ids), User.role.in_([role.value for role in COOPERATIVE_ROLES]))
            .group_by(User.cooperative_id)
        ).all()
    }

    member_agg = {
        row.cooperative_id: int(row.members_count or 0)
        for row in db.execute(
            select(Member.cooperative_id, func.count(Member.id).label("members_count"))
            .where(Member.cooperative_id.in_(cooperative_ids))
            .group_by(Member.cooperative_id)
        ).all()
    }

    parcel_agg = {
        row.cooperative_id: int(row.parcels_count or 0)
        for row in db.execute(
            select(Parcel.cooperative_id, func.count(Parcel.id).label("parcels_count"))
            .where(Parcel.cooperative_id.in_(cooperative_ids))
            .group_by(Parcel.cooperative_id)
        ).all()
    }

    batch_agg = {
        row.cooperative_id: row
        for row in db.execute(
            select(
                Batch.cooperative_id,
                func.count(Batch.id).label("lots_count"),
                func.sum(case((Batch.status.in_(["created", "in_progress"]), 1), else_=0)).label("active_lots_count"),
                func.sum(
                    case(
                        (
                            (Batch.preharvest_completed_at.is_not(None)) & (Batch.confirmed_weight_kg.is_not(None)),
                            1,
                        ),
                        else_=0,
                    )
                ).label("ready_post_recolte_lots_count"),
                func.coalesce(func.sum(Batch.initial_qty), 0.0).label("total_initial_qty"),
                func.coalesce(func.sum(Batch.current_qty), 0.0).label("total_current_qty"),
            )
            .where(Batch.cooperative_id.in_(cooperative_ids))
            .group_by(Batch.cooperative_id)
        ).all()
    }

    stock_agg = {
        row.cooperative_id: row
        for row in db.execute(
            select(
                Stock.cooperative_id,
                func.coalesce(func.sum(Stock.total_stock_kg), 0.0).label("total_stock_kg"),
                func.coalesce(func.sum(Stock.total_stock_kg - Stock.reserved_in_lots_kg), 0.0).label("available_stock_kg"),
                func.coalesce(func.sum(case((Stock.total_stock_kg - Stock.reserved_in_lots_kg < (Stock.total_stock_kg * 0.2), 1), else_=0)), 0).label("low_stock_alerts_count"),
            )
            .where(Stock.cooperative_id.in_(cooperative_ids))
            .group_by(Stock.cooperative_id)
        ).all()
    }

    recommendation_agg = {
        row.cooperative_id: int(row.recommendations_count or 0)
        for row in db.execute(
            select(Batch.cooperative_id, func.count(Recommendation.id).label("recommendations_count"))
            .join(Recommendation, Recommendation.batch_id == Batch.id)
            .where(Batch.cooperative_id.in_(cooperative_ids))
            .group_by(Batch.cooperative_id)
        ).all()
    }

    return user_agg, member_agg, parcel_agg, batch_agg, stock_agg, recommendation_agg


def build_cooperative_oversight(db: Session, cooperatives: list[Cooperative]) -> CooperativeOversightResponse:
    if not cooperatives:
        return CooperativeOversightResponse(
            summary=OversightSummary(
                total_cooperatives=0,
                total_users=0,
                total_managers=0,
                total_members=0,
                total_parcels=0,
                total_lots=0,
                active_lots=0,
                ready_post_recolte_lots=0,
                total_available_stock_kg=0.0,
                total_stock_kg=0.0,
                avg_loss_rate=0.0,
                avg_efficiency_rate=0.0,
                low_stock_alerts_count=0,
                recommendations_count=0,
            ),
            cooperatives=[],
        )

    institution_ids = [coop.institution_id for coop in cooperatives if coop.institution_id is not None]
    institution_by_id = {
        item.id: item.name
        for item in db.scalars(select(Institution).where(Institution.id.in_(institution_ids))).all()
    }

    cooperative_ids = [coop.id for coop in cooperatives]
    user_agg, member_agg, parcel_agg, batch_agg, stock_agg, recommendation_agg = _cooperative_rows(db, cooperative_ids)

    rows: list[CooperativeOversightRow] = []

    summary_users = 0
    summary_managers = 0
    summary_members = 0
    summary_parcels = 0
    summary_lots = 0
    summary_active_lots = 0
    summary_ready_post = 0
    summary_available_stock = 0.0
    summary_total_stock = 0.0
    summary_low_stock_alerts = 0
    summary_recommendations = 0
    summary_loss_sum = 0.0
    summary_efficiency_sum = 0.0

    for coop in cooperatives:
        user_row = user_agg.get(coop.id)
        users_count = int(user_row.users_count or 0) if user_row else 0
        managers_count = int(user_row.managers_count or 0) if user_row else 0
        viewers_count = int(user_row.viewers_count or 0) if user_row else 0

        members_count = int(member_agg.get(coop.id, 0))
        parcels_count = int(parcel_agg.get(coop.id, 0))

        batch_row = batch_agg.get(coop.id)
        lots_count = int(batch_row.lots_count or 0) if batch_row else 0
        active_lots_count = int(batch_row.active_lots_count or 0) if batch_row else 0
        ready_post_count = int(batch_row.ready_post_recolte_lots_count or 0) if batch_row else 0
        total_initial_qty = float(batch_row.total_initial_qty or 0.0) if batch_row else 0.0
        total_current_qty = float(batch_row.total_current_qty or 0.0) if batch_row else 0.0
        loss_rate, efficiency_rate = _loss_efficiency(total_initial_qty, total_current_qty)

        stock_row = stock_agg.get(coop.id)
        total_stock_kg = round_metric(float(stock_row.total_stock_kg or 0.0)) if stock_row else 0.0
        available_stock_kg = round_metric(float(stock_row.available_stock_kg or 0.0)) if stock_row else 0.0
        low_stock_alerts_count = int(stock_row.low_stock_alerts_count or 0) if stock_row else 0

        recommendations_count = int(recommendation_agg.get(coop.id, 0))

        rows.append(
            CooperativeOversightRow(
                cooperative_id=coop.id,
                cooperative_name=coop.name,
                institution_id=coop.institution_id,
                institution_name=institution_by_id.get(coop.institution_id) if coop.institution_id else None,
                status=coop.status.value if hasattr(coop.status, "value") else str(coop.status),
                users_count=users_count,
                managers_count=managers_count,
                viewers_count=viewers_count,
                members_count=members_count,
                parcels_count=parcels_count,
                lots_count=lots_count,
                active_lots_count=active_lots_count,
                ready_post_recolte_lots_count=ready_post_count,
                available_stock_kg=available_stock_kg,
                total_stock_kg=total_stock_kg,
                loss_rate=loss_rate,
                efficiency_rate=efficiency_rate,
                low_stock_alerts_count=low_stock_alerts_count,
                recommendations_count=recommendations_count,
            )
        )

        summary_users += users_count
        summary_managers += managers_count
        summary_members += members_count
        summary_parcels += parcels_count
        summary_lots += lots_count
        summary_active_lots += active_lots_count
        summary_ready_post += ready_post_count
        summary_available_stock += available_stock_kg
        summary_total_stock += total_stock_kg
        summary_low_stock_alerts += low_stock_alerts_count
        summary_recommendations += recommendations_count
        summary_loss_sum += loss_rate
        summary_efficiency_sum += efficiency_rate

    coop_count = len(rows)

    return CooperativeOversightResponse(
        summary=OversightSummary(
            total_cooperatives=coop_count,
            total_users=summary_users,
            total_managers=summary_managers,
            total_members=summary_members,
            total_parcels=summary_parcels,
            total_lots=summary_lots,
            active_lots=summary_active_lots,
            ready_post_recolte_lots=summary_ready_post,
            total_available_stock_kg=round_metric(summary_available_stock),
            total_stock_kg=round_metric(summary_total_stock),
            avg_loss_rate=round_metric(summary_loss_sum / coop_count) if coop_count else 0.0,
            avg_efficiency_rate=round_metric(summary_efficiency_sum / coop_count) if coop_count else 0.0,
            low_stock_alerts_count=summary_low_stock_alerts,
            recommendations_count=summary_recommendations,
        ),
        cooperatives=rows,
    )
