import { PrismaClient, CollecteStatut, CooperativeStatus, EtapeStatut, FactureStatut, FluxType, LotStatut, MembreStatut, RecommandationStatut, TachePriorite, TacheStatut, UserRole, UserStatus } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

function date(value: string) {
  return new Date(`${value}T09:00:00.000Z`);
}

async function main() {
  await prisma.fluxMatiere.deleteMany();
  await prisma.knowledgeChunk.deleteMany();
  await prisma.referenceMetric.deleteMany();
  await prisma.etapeLot.deleteMany();
  await prisma.recommandationIA.deleteMany();
  await prisma.facture.deleteMany();
  await prisma.tache.deleteMany();
  await prisma.evenementCalendrier.deleteMany();
  await prisma.tresorerie.deleteMany();
  await prisma.stock.deleteMany();
  await prisma.collecte.deleteMany();
  await prisma.lot.deleteMany();
  await prisma.parcelle.deleteMany();
  await prisma.produit.deleteMany();
  await prisma.membre.deleteMany();
  await prisma.user.deleteMany();
  await prisma.cooperative.deleteMany();

  const cooperative = await prisma.cooperative.create({
    data: {
      name: "WeeFarm Operations Cooperative",
      region: "Thies",
      mode: "pilotage",
      address: "Thies, Senegal",
      phone: "+221 77 420 10 22",
      status: CooperativeStatus.ACTIVE,
    },
  });

  const managerPasswordHash = await bcrypt.hash("Manager123!", 10);
  const adminPasswordHash = await bcrypt.hash("Admin123!", 10);
  const agentPasswordHash = await bcrypt.hash("Agent123!", 10);

  const adminUser = await prisma.user.create({
    data: {
      fullName: "Admin WeeFarm",
      email: "admin@weefarm.local",
      passwordHash: adminPasswordHash,
      role: UserRole.ADMIN,
      status: UserStatus.ACTIVE,
      cooperativeId: cooperative.id,
      phone: "+221 70 000 00 01",
    },
  });

  const managerUser = await prisma.user.create({
    data: {
      fullName: "mohamed ali bouzir",
      email: "mohamed@weefarm.sn",
      passwordHash: managerPasswordHash,
      role: UserRole.MANAGER,
      status: UserStatus.ACTIVE,
      cooperativeId: cooperative.id,
      phone: "+221 77 000 10 20",
    },
  });

  const agentUser = await prisma.user.create({
    data: {
      fullName: "Cheikh Ndiaye",
      email: "agent@weefarm.sn",
      passwordHash: agentPasswordHash,
      role: UserRole.AGENT,
      status: UserStatus.ACTIVE,
      cooperativeId: cooperative.id,
      phone: "+221 77 100 11 22",
    },
  });

  const membersSeed = [
    { code: "MBR-001", nom: "Diop", prenom: "Mamadou", phone: "+221770010001", village: "Notto", culture: "Mangue", area: 1.8, parcel: 2 },
    { code: "MBR-002", nom: "Ndiaye", prenom: "Fatou", phone: "+221770010002", village: "Fandene", culture: "Oignon", area: 1.2, parcel: 1 },
    { code: "MBR-003", nom: "Seck", prenom: "Abdou", phone: "+221770010003", village: "Pout", culture: "Arachide", area: 2.3, parcel: 3 },
    { code: "MBR-004", nom: "Ba", prenom: "Ibrahima", phone: "+221770010004", village: "Keur Moussa", culture: "Bissap", area: 1.0, parcel: 1 },
    { code: "MBR-005", nom: "Sarr", prenom: "Aissatou", phone: "+221770010005", village: "Tivaouane Peulh", culture: "Mil", area: 1.6, parcel: 2 },
  ];

  const members = [] as Array<{ id: string; fullName: string; culture: string }>;
  for (const entry of membersSeed) {
    const created = await prisma.membre.create({
      data: {
        cooperativeId: cooperative.id,
        code: entry.code,
        nom: entry.nom,
        prenom: entry.prenom,
        fullName: `${entry.prenom} ${entry.nom}`,
        phone: entry.phone,
        village: entry.village,
        culturePrincipale: entry.culture,
        mainProduct: entry.culture,
        parcelCount: entry.parcel,
        areaHectares: entry.area,
        joinDate: date("2026-01-05"),
        specialty: "Production cooperative",
        statut: MembreStatut.ACTIF,
      },
    });
    members.push({ id: created.id, fullName: created.fullName, culture: entry.culture });

    await prisma.parcelle.create({
      data: {
        memberId: created.id,
        cooperativeId: cooperative.id,
        location: `${entry.village} - Parcelle ${entry.code.slice(-1)}`,
        area: entry.area,
        soilType: "argilo-sableux",
        irrigationType: "goutte-a-goutte",
      },
    });
  }

  const productsSeed = [
    { name: "Mangue", category: "Fruits", unit: "kg", grade: "A" },
    { name: "Oignon", category: "Legumes", unit: "kg", grade: "A" },
    { name: "Arachide", category: "Cereales", unit: "kg", grade: "B" },
    { name: "Bissap", category: "Plantes", unit: "kg", grade: "A" },
    { name: "Mil", category: "Cereales", unit: "kg", grade: "B" },
  ];

  const products = new Map<string, { id: string; name: string }>();
  for (const product of productsSeed) {
    const created = await prisma.produit.create({
      data: {
        cooperativeId: cooperative.id,
        name: product.name,
        category: product.category,
        unit: product.unit,
        qualityGrade: product.grade,
      },
    });
    products.set(product.name, { id: created.id, name: created.name });
  }

  const collectesSeed = [
    ["2026-01-05", "Mangue", 420, 0], ["2026-01-08", "Oignon", 380, 1], ["2026-01-10", "Arachide", 310, 2], ["2026-01-12", "Bissap", 120, 3], ["2026-01-15", "Mil", 290, 4],
    ["2026-01-20", "Mangue", 510, 0], ["2026-01-22", "Oignon", 405, 1], ["2026-01-25", "Arachide", 355, 2],
    ["2026-02-01", "Mangue", 560, 0], ["2026-02-03", "Oignon", 390, 1], ["2026-02-05", "Arachide", 345, 2], ["2026-02-08", "Bissap", 138, 3], ["2026-02-11", "Mil", 275, 4],
    ["2026-02-15", "Mangue", 640, 0], ["2026-02-18", "Oignon", 412, 1], ["2026-02-20", "Arachide", 372, 2],
    ["2026-03-01", "Mangue", 710, 0], ["2026-03-04", "Oignon", 430, 1], ["2026-03-06", "Arachide", 398, 2], ["2026-03-08", "Bissap", 152, 3], ["2026-03-11", "Mil", 302, 4],
    ["2026-03-15", "Mangue", 680, 0], ["2026-03-18", "Oignon", 455, 1], ["2026-03-22", "Arachide", 410, 2],
  ] as const;

  for (const [dateValue, productName, quantity, memberIndex] of collectesSeed) {
    const member = members[memberIndex];
    const product = products.get(productName)!;
    const status = quantity % 2 === 0 ? CollecteStatut.VALIDE : CollecteStatut.EN_ATTENTE;

    await prisma.collecte.create({
      data: {
        cooperativeId: cooperative.id,
        membreId: member.id,
        produitId: product.id,
        produit: product.name,
        quantiteKg: quantity,
        statut: status,
        date: date(dateValue),
        agentId: agentUser.id,
        grade: productName === "Mangue" ? "A" : "B",
        estimatedValueFcfa: Math.round(quantity * 550),
      },
    });
  }

  const stockSeed = [
    { produit: "Mangue", qty: 1240, seuil: 350, max: 2500 },
    { produit: "Oignon", qty: 380, seuil: 300, max: 1800 },
    { produit: "Arachide", qty: 650, seuil: 320, max: 1900 },
    { produit: "Bissap", qty: 95, seuil: 120, max: 700 },
    { produit: "Mil", qty: 45, seuil: 110, max: 600 },
  ];

  for (const stock of stockSeed) {
    const product = products.get(stock.produit)!;
    await prisma.stock.create({
      data: {
        cooperativeId: cooperative.id,
        produitId: product.id,
        produit: stock.produit,
        quantiteActuelleKg: stock.qty,
        seuilCritiqueKg: stock.seuil,
        quantiteMaxKg: stock.max,
        unit: "kg",
        lastUpdated: date("2026-03-30"),
      },
    });
  }

  const lotMangue = await prisma.lot.create({
    data: {
      cooperativeId: cooperative.id,
      productId: products.get("Mangue")!.id,
      code: "LOT-MG-001",
      produit: "Mangue",
      quantiteInitialeKg: 3200,
      quantiteActuelleKg: 2580,
      statut: LotStatut.ACTIF,
      creationDate: date("2026-03-01"),
      createdByUserId: managerUser.id,
    },
  });

  const lotOignon = await prisma.lot.create({
    data: {
      cooperativeId: cooperative.id,
      productId: products.get("Oignon")!.id,
      code: "LOT-OI-001",
      produit: "Oignon",
      quantiteInitialeKg: 2600,
      quantiteActuelleKg: 2185,
      statut: LotStatut.ACTIF,
      creationDate: date("2026-03-02"),
      createdByUserId: managerUser.id,
    },
  });

  const lotEtapes = [
    {
      lotId: lotMangue.id,
      stages: [
        { nom: "Tri", type: "tri", ordre: 1, qin: 3200, qout: 3160, perte: 40, debut: "2026-03-03", fin: "2026-03-03", statut: EtapeStatut.TERMINE },
        { nom: "Sechage", type: "sechage", ordre: 2, qin: 3160, qout: 3020, perte: 140, debut: "2026-03-04", fin: "2026-03-04", statut: EtapeStatut.TERMINE },
        { nom: "Nettoyage", type: "nettoyage", ordre: 3, qin: 3020, qout: 2840, perte: 180, debut: "2026-03-05", fin: "2026-03-05", statut: EtapeStatut.TERMINE },
        { nom: "Conditionnement", type: "conditionnement", ordre: 4, qin: 2840, qout: 2580, perte: 260, debut: "2026-03-06", fin: "2026-03-06", statut: EtapeStatut.TERMINE },
      ],
    },
    {
      lotId: lotOignon.id,
      stages: [
        { nom: "Tri", type: "tri", ordre: 1, qin: 2600, qout: 2535, perte: 65, debut: "2026-03-03", fin: "2026-03-03", statut: EtapeStatut.TERMINE },
        { nom: "Sechage", type: "sechage", ordre: 2, qin: 2535, qout: 2410, perte: 125, debut: "2026-03-04", fin: "2026-03-04", statut: EtapeStatut.TERMINE },
        { nom: "Nettoyage", type: "nettoyage", ordre: 3, qin: 2410, qout: 2290, perte: 120, debut: "2026-03-05", fin: "2026-03-05", statut: EtapeStatut.TERMINE },
        { nom: "Conditionnement", type: "conditionnement", ordre: 4, qin: 2290, qout: 2185, perte: 105, debut: "2026-03-06", fin: "2026-03-06", statut: EtapeStatut.EN_COURS },
      ],
    },
  ] as const;

  for (const lotData of lotEtapes) {
    for (const stage of lotData.stages) {
      const created = await prisma.etapeLot.create({
        data: {
          lotId: lotData.lotId,
          nomEtape: stage.nom,
          type: stage.type,
          ordre: stage.ordre,
          quantiteEntreeKg: stage.qin,
          quantiteSortieKg: stage.qout,
          perteKg: stage.perte,
          statut: stage.statut,
          dateDebut: date(stage.debut),
          dateFin: date(stage.fin),
          notes: `Suivi ${stage.nom.toLowerCase()} lot ${lotData.lotId.slice(0, 6)}`,
        },
      });

      await prisma.fluxMatiere.create({
        data: {
          lotId: lotData.lotId,
          etapeId: created.id,
          type: stage.ordre <= 2 ? FluxType.PRE_RECOLTE : FluxType.POST_RECOLTE,
          date: date(stage.debut),
          notes: `Flux matiere ${stage.nom}`,
        },
      });
    }
  }

  await prisma.tresorerie.createMany({
    data: [
      { cooperativeId: cooperative.id, mois: 1, annee: 2026, recettesFcfa: 1450000, depensesFcfa: 910000, soldeFcfa: 540000 },
      { cooperativeId: cooperative.id, mois: 2, annee: 2026, recettesFcfa: 1620000, depensesFcfa: 980000, soldeFcfa: 640000 },
      { cooperativeId: cooperative.id, mois: 3, annee: 2026, recettesFcfa: 1810000, depensesFcfa: 1007000, soldeFcfa: 803000 },
    ],
  });

  await prisma.facture.createMany({
    data: [
      { cooperativeId: cooperative.id, numero: "FAC-2026-001", membreId: members[0].id, montantFcfa: 288000, statut: FactureStatut.EN_ATTENTE, dateEmission: date("2026-03-07") },
      { cooperativeId: cooperative.id, numero: "FAC-2026-002", membreId: members[1].id, montantFcfa: 192000, statut: FactureStatut.ENCAISSEE, dateEmission: date("2026-03-10") },
      { cooperativeId: cooperative.id, numero: "FAC-2026-003", membreId: members[2].id, montantFcfa: 265000, statut: FactureStatut.EN_ATTENTE, dateEmission: date("2026-03-19") },
    ],
  });

  await prisma.tache.createMany({
    data: [
      { cooperativeId: cooperative.id, titre: "Verifier lot Mangue", description: "Controler la perte etape conditionnement", assigneeId: managerUser.id, statut: TacheStatut.EN_COURS, dueDate: date("2026-04-21"), priorite: TachePriorite.HAUTE },
      { cooperativeId: cooperative.id, titre: "Valider collectes semaine", description: "Passer EN_ATTENTE vers VALIDE", assigneeId: agentUser.id, statut: TacheStatut.A_FAIRE, dueDate: date("2026-04-22"), priorite: TachePriorite.MOYENNE },
      { cooperativeId: cooperative.id, titre: "Mise a jour stock Bissap", description: "Controle physique du magasin", assigneeId: agentUser.id, statut: TacheStatut.A_FAIRE, dueDate: date("2026-04-24"), priorite: TachePriorite.HAUTE },
      { cooperativeId: cooperative.id, titre: "Preparation reunion cooperative", description: "Consolider indicateurs mars", assigneeId: managerUser.id, statut: TacheStatut.TERMINEE, dueDate: date("2026-04-18"), priorite: TachePriorite.MOYENNE },
      { cooperativeId: cooperative.id, titre: "Planification irrigation", description: "Coordonner avec equipes terrain", assigneeId: managerUser.id, statut: TacheStatut.EN_COURS, dueDate: date("2026-04-27"), priorite: TachePriorite.BASSE },
    ],
  });

  await prisma.evenementCalendrier.createMany({
    data: [
      { cooperativeId: cooperative.id, titre: "Controle qualite lot Mangue", date: date("2026-04-23"), type: "qualite", description: "Verification lot LOT-MG-001" },
      { cooperativeId: cooperative.id, titre: "Reunion hebdomadaire cooperative", date: date("2026-04-28"), type: "reunion", description: "Suivi KPI et pertes" },
      { cooperativeId: cooperative.id, titre: "Campagne collecte Oignon", date: date("2026-05-09"), type: "collecte", description: "Demarrage nouvelle vague de collecte" },
    ],
  });

  await prisma.recommandationIA.create({
    data: {
      cooperativeId: cooperative.id,
      lotId: lotMangue.id,
      texte: "Aucune action critique. Maintenir le process actuel.",
      statut: RecommandationStatut.STABLE,
      impactedStep: "Conditionnement",
      rationale: "Taux de perte maitrise et stock global sous controle.",
      expectedImpact: "+0.5 pt efficacite estimee",
      generatedAt: date("2026-03-31"),
    },
  });

  await prisma.referenceMetric.createMany({
    data: [
      {
        sourceId: "ANSD-THIES-2026-01",
        country: "Senegal",
        region: "Thies",
        crop: "Mangue",
        metric: "post_harvest_loss_pct",
        period: "2026-Q1",
        value: 8.6,
        unit: "%",
        notes: "Pertes moyennes post-recolte sur echantillon cooperative.",
      },
      {
        sourceId: "FAOSTAT-SN-2026-02",
        country: "Senegal",
        region: "Thies",
        crop: "Oignon",
        metric: "storage_loss_pct",
        period: "2026-Q1",
        value: 6.3,
        unit: "%",
        notes: "Perte en stockage en chambre froide.",
      },
      {
        sourceId: "ISRA-KAOLACK-2026-03",
        country: "Senegal",
        region: "Kaolack",
        crop: "Arachide",
        metric: "drying_target_moisture",
        period: "2026-Q1",
        value: 9.5,
        unit: "%",
        notes: "Humidite cible recommandee pour conservation.",
      },
    ],
  });

  await prisma.knowledgeChunk.createMany({
    data: [
      {
        sourceId: "KB-SN-001",
        sourceUrl: "https://weefarm.sn/knowledge/post-harvest-mangue",
        country: "Senegal",
        region: "Thies",
        crop: "Mangue",
        topic: "post_recolte",
        content:
          "Pour la mangue, limiter le temps entre tri et conditionnement, maintenir humidite entre 12% et 14%, et eviter les chocs thermiques.",
      },
      {
        sourceId: "KB-SN-002",
        sourceUrl: "https://weefarm.sn/knowledge/oignon-stockage",
        country: "Senegal",
        region: "Thies",
        crop: "Oignon",
        topic: "stockage",
        content:
          "Stocker l'oignon avec ventilation constante. Verifier chaque lot tous les 48h pour detecter humidite et debuts de pourriture.",
      },
      {
        sourceId: "KB-SN-003",
        sourceUrl: "https://weefarm.sn/knowledge/arachide-sechage",
        country: "Senegal",
        region: "Kaolack",
        crop: "Arachide",
        topic: "sechage",
        content:
          "Le sechage progressif en couches fines reduit les pertes. Cible recommandee: humidite finale inferieure a 10%.",
      },
    ],
  });

  void adminUser;
  void managerUser;
}

main()
  .catch((error) => {
    process.stderr.write(`${String(error)}\n`);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
