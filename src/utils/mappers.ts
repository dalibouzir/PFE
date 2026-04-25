import type { Collecte, Cooperative, EtapeLot, Lot, Membre, Produit, RecommandationIA, Stock, User } from "@prisma/client";

export function mapCooperative(coop: Cooperative) {
  return {
    id: coop.id,
    name: coop.name,
    region: coop.region,
    address: coop.address ?? "",
    phone: coop.phone ?? "",
    status: coop.status.toLowerCase(),
    created_at: coop.createdAt.toISOString(),
    updated_at: coop.updatedAt.toISOString(),
  };
}

export function mapUser(user: User) {
  return {
    id: user.id,
    full_name: user.fullName,
    email: user.email,
    phone: user.phone,
    role: user.role.toLowerCase(),
    status: user.status.toLowerCase(),
    cooperative_id: user.cooperativeId,
    created_at: user.createdAt.toISOString(),
    updated_at: user.updatedAt.toISOString(),
  };
}

export function mapMember(member: Membre) {
  return {
    id: member.id,
    cooperative_id: member.cooperativeId,
    code: member.code,
    full_name: member.fullName,
    phone: member.phone,
    village: member.village,
    main_product: member.mainProduct,
    parcel_count: member.parcelCount,
    area_hectares: member.areaHectares,
    join_date: member.joinDate?.toISOString().slice(0, 10) ?? null,
    specialty: member.specialty,
    status: member.statut === "ACTIF" ? "active" : member.statut === "INACTIF" ? "inactive" : "seasonal",
    created_at: member.createdAt.toISOString(),
    updated_at: member.updatedAt.toISOString(),
  };
}

export function mapProduct(product: Produit) {
  return {
    id: product.id,
    cooperative_id: product.cooperativeId,
    name: product.name,
    category: product.category,
    unit: product.unit,
    quality_grade: product.qualityGrade,
    created_at: product.createdAt.toISOString(),
    updated_at: product.updatedAt.toISOString(),
  };
}

export function mapCollecte(input: Collecte) {
  return {
    id: input.id,
    cooperative_id: input.cooperativeId,
    member_id: input.membreId,
    product_id: input.produitId,
    date: input.date.toISOString().slice(0, 10),
    quantity: input.quantiteKg,
    grade: input.grade,
    estimated_value: input.estimatedValueFcfa,
    status: input.statut === "VALIDE" ? "VALIDE" : "EN_ATTENTE",
    created_at: input.createdAt.toISOString(),
    updated_at: input.updatedAt.toISOString(),
    produit: input.produit,
  };
}

export function mapStock(stock: Stock) {
  return {
    id: stock.id,
    cooperative_id: stock.cooperativeId,
    product_id: stock.produitId,
    quantity: stock.quantiteActuelleKg,
    threshold: stock.seuilCritiqueKg,
    quantity_max: stock.quantiteMaxKg,
    unit: stock.unit,
    produit: stock.produit,
    last_updated: stock.lastUpdated.toISOString(),
    created_at: stock.createdAt.toISOString(),
    updated_at: stock.updatedAt.toISOString(),
  };
}

export function mapLot(batch: Lot) {
  return {
    id: batch.id,
    cooperative_id: batch.cooperativeId,
    product_id: batch.productId,
    code: batch.code,
    creation_date: batch.creationDate.toISOString().slice(0, 10),
    initial_qty: batch.quantiteInitialeKg,
    current_qty: batch.quantiteActuelleKg,
    status: batch.statut === "ACTIF" ? "in_progress" : "completed",
    created_by_user_id: batch.createdByUserId,
    created_at: batch.createdAt.toISOString(),
    updated_at: batch.updatedAt.toISOString(),
    produit: batch.produit,
  };
}

export function mapEtape(step: EtapeLot) {
  const qtyIn = step.quantiteEntreeKg;
  const qtyOut = step.quantiteSortieKg;
  const waste = step.perteKg;
  const lossPct = qtyIn > 0 ? (waste / qtyIn) * 100 : 0;
  const efficiencyPct = qtyIn > 0 ? (qtyOut / qtyIn) * 100 : 0;

  return {
    id: step.id,
    batch_id: step.lotId,
    type: step.type,
    date: step.dateDebut.toISOString().slice(0, 10),
    qty_in: qtyIn,
    qty_out: qtyOut,
    waste_qty: waste,
    notes: step.notes,
    status: step.statut === "TERMINE" ? "completed" : "in_progress",
    duration_minutes:
      step.dateFin && step.dateDebut
        ? Math.max(1, Math.round((step.dateFin.getTime() - step.dateDebut.getTime()) / 60000))
        : null,
    created_at: step.createdAt.toISOString(),
    updated_at: step.updatedAt.toISOString(),
    loss_pct: Number(lossPct.toFixed(2)),
    efficiency_pct: Number(efficiencyPct.toFixed(2)),
    warning: lossPct >= 8,
    nom_etape: step.nomEtape,
    ordre: step.ordre,
  };
}

export function mapRecommendation(rec: RecommandationIA) {
  return {
    id: rec.id,
    batch_id: rec.lotId,
    loss_pct: 0,
    efficiency_pct: 0,
    anomaly_detected: rec.statut !== "STABLE",
    anomaly_score: rec.statut === "CRITIQUE" ? 80 : rec.statut === "ATTENTION" ? 45 : 10,
    risk_level: rec.statut.toLowerCase(),
    suggested_action: rec.texte,
    rationale: rec.rationale ?? "Recommandation issue de l'analyse operationnelle.",
    reasons: [rec.rationale ?? "Analyse des stocks, pertes et collectes."],
    status: rec.statut,
    generated_at: rec.generatedAt.toISOString(),
  };
}
