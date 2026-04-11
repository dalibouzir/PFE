export type PlatformRole = "admin" | "manager";

export type ProductName = "Mangue" | "Arachide" | "Mil";

export type Grade = "A" | "B" | "C";

export type CooperativeStatus = "Active" | "En onboarding" | "Suspendue";

export type ManagerStatus = "Actif" | "Suspendu" | "Invitation envoyee";

export type MemberStatus = "Actif" | "Inactif" | "Saisonnier";

export type InputStatus = "Valide" | "Controle qualite" | "En attente";

export type StockStatus = "Correct" | "A surveiller" | "Critique";

export type LotStatus = "Collecte" | "En transformation" | "Pret" | "Bloque";

export type StageName = "nettoyage" | "sechage" | "tri" | "emballage";

export type StageState = "termine" | "en cours" | "a venir";

export type BadgeTone = "success" | "warning" | "danger" | "neutral" | "info";

export type StatCard = {
  id: string;
  label: string;
  value: number;
  suffix?: string;
  trend: string;
};

export type CooperativeRecord = {
  id: string;
  name: string;
  region: "Thies" | "Louga" | "Casamance" | "Kaolack" | "Saint-Louis";
  createdAt: string;
  managersCount: number;
  status: CooperativeStatus;
  membersCount: number;
};

export type ManagerAccount = {
  id: string;
  name: string;
  email: string;
  phone: string;
  cooperative: string;
  region: CooperativeRecord["region"];
  status: ManagerStatus;
  lastActive: string;
};

export type ActivityItem = {
  id: string;
  title: string;
  detail: string;
  date: string;
  tone: BadgeTone;
};

export type MemberRecord = {
  id: string;
  nom: string;
  telephone: string;
  zone: string;
  culturePrincipale: ProductName;
  parcelles: number;
  superficieTotaleHa: number;
  statut: MemberStatus;
};

export type ParcelRecord = {
  id: string;
  code: string;
  memberId: string;
  memberNom: string;
  localisation: string;
  superficieHa: number;
  typeSol: string;
  cultureActuelle: ProductName;
  statut: "Active" | "Preparation" | "Repos";
};

export type ProductOverview = {
  produit: ProductName;
  volumeCollecteTonnes: number;
  stockActuelTonnes: number;
  lotsActifs: number;
  perteMoyennePct: number;
  gradeA: number;
  gradeB: number;
  gradeC: number;
};

export type InputRecord = {
  id: string;
  date: string;
  membre: string;
  memberId: string;
  produit: ProductName;
  quantiteKg: number;
  grade: Grade;
  valeurEstimeeFcfa: number;
  statut: InputStatus;
};

export type StockRecord = {
  id: string;
  produit: ProductName;
  grade: Grade;
  quantiteTonnes: number;
  seuilTonnes: number;
  statut: StockStatus;
  entrepot: string;
  derniereMiseAJour: string;
};

export type LotRecord = {
  id: string;
  code: string;
  produit: ProductName;
  createdAt: string;
  initialQuantityKg: number;
  currentQuantityKg: number;
  status: LotStatus;
  progressionPct: number;
  gradeDominant: Grade;
  memberNom: string;
};

export type LotStageHistory = {
  stage: StageName;
  startedAt: string;
  endedAt: string | null;
  state: StageState;
  rendementPct: number;
};

export type TransformationRecord = {
  lotCode: string;
  produit: ProductName;
  quantiteKg: number;
  statut: LotStatus;
  stageActuelle: StageName;
  operateur: string;
  historique: LotStageHistory[];
};

export type QuickAction = {
  label: string;
  href: string;
  tone?: "default" | "accent";
};

export type AssistantMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  time: string;
  points?: string[];
};

export type AssistantThread = {
  id: string;
  title: string;
  updatedAt: string;
  preview: string;
  messages: AssistantMessage[];
};

export const adminDashboardKpis: StatCard[] = [
  { id: "coops", label: "Total cooperatives", value: 18, trend: "+2 ce mois" },
  { id: "managers", label: "Managers actifs", value: 31, trend: "89% actifs cette semaine" },
  { id: "new", label: "Nouvelles cooperatives", value: 3, trend: "30 derniers jours" },
  { id: "disabled", label: "Comptes desactives", value: 4, trend: "-1 vs mois dernier" },
];

export const cooperativeRecords: CooperativeRecord[] = [
  {
    id: "COOP-TH-014",
    name: "Cooperative Deggo Thies",
    region: "Thies",
    createdAt: "2024-09-11",
    managersCount: 2,
    status: "Active",
    membersCount: 126,
  },
  {
    id: "COOP-LG-006",
    name: "Union Wattu Louga",
    region: "Louga",
    createdAt: "2025-01-18",
    managersCount: 1,
    status: "Active",
    membersCount: 87,
  },
  {
    id: "COOP-CS-003",
    name: "GIE Kolda Casamance",
    region: "Casamance",
    createdAt: "2025-03-02",
    managersCount: 2,
    status: "En onboarding",
    membersCount: 64,
  },
  {
    id: "COOP-SL-004",
    name: "Fruitiers du Delta",
    region: "Saint-Louis",
    createdAt: "2024-07-26",
    managersCount: 3,
    status: "Active",
    membersCount: 141,
  },
  {
    id: "COOP-KL-010",
    name: "Arachide Sine Saloum",
    region: "Kaolack",
    createdAt: "2025-06-10",
    managersCount: 1,
    status: "Suspendue",
    membersCount: 79,
  },
  {
    id: "COOP-CS-011",
    name: "Terroirs de Bignona",
    region: "Casamance",
    createdAt: "2025-11-20",
    managersCount: 1,
    status: "Active",
    membersCount: 58,
  },
];

export const managerAccounts: ManagerAccount[] = [
  {
    id: "MGR-001",
    name: "Aissatou Ndiaye",
    email: "a.ndiaye@deggo.sn",
    phone: "+221 77 445 81 30",
    cooperative: "Cooperative Deggo Thies",
    region: "Thies",
    status: "Actif",
    lastActive: "2026-04-10 17:22",
  },
  {
    id: "MGR-002",
    name: "Mamadou Faye",
    email: "m.faye@deggo.sn",
    phone: "+221 70 384 67 12",
    cooperative: "Cooperative Deggo Thies",
    region: "Thies",
    status: "Actif",
    lastActive: "2026-04-10 15:04",
  },
  {
    id: "MGR-003",
    name: "Khady Ba",
    email: "kh.ba@wattu.sn",
    phone: "+221 76 629 04 88",
    cooperative: "Union Wattu Louga",
    region: "Louga",
    status: "Actif",
    lastActive: "2026-04-10 10:36",
  },
  {
    id: "MGR-004",
    name: "Ibrahima Cisse",
    email: "i.cisse@kolda-casa.sn",
    phone: "+221 78 510 93 44",
    cooperative: "GIE Kolda Casamance",
    region: "Casamance",
    status: "Invitation envoyee",
    lastActive: "-",
  },
  {
    id: "MGR-005",
    name: "Sokhna Sarr",
    email: "s.sarr@delta.sn",
    phone: "+221 75 929 81 05",
    cooperative: "Fruitiers du Delta",
    region: "Saint-Louis",
    status: "Actif",
    lastActive: "2026-04-09 18:12",
  },
  {
    id: "MGR-006",
    name: "Cheikh Dieng",
    email: "c.dieng@arachide-sine.sn",
    phone: "+221 70 915 22 50",
    cooperative: "Arachide Sine Saloum",
    region: "Kaolack",
    status: "Suspendu",
    lastActive: "2026-03-21 09:41",
  },
];

export const adminRecentActivity: ActivityItem[] = [
  {
    id: "ACT-01",
    title: "Nouvelle cooperative creee",
    detail: "Terroirs de Bignona ajoutee en Casamance",
    date: "10 avr 2026",
    tone: "success",
  },
  {
    id: "ACT-02",
    title: "Compte manager suspendu",
    detail: "Cheikh Dieng (Arachide Sine Saloum)",
    date: "09 avr 2026",
    tone: "warning",
  },
  {
    id: "ACT-03",
    title: "Invitation manager envoyee",
    detail: "Ibrahima Cisse - GIE Kolda Casamance",
    date: "09 avr 2026",
    tone: "info",
  },
  {
    id: "ACT-04",
    title: "Mise a jour parametres plateforme",
    detail: "Regles d alertes critiques harmonisees",
    date: "08 avr 2026",
    tone: "neutral",
  },
];

export const adminRegionOverview = [
  { region: "Thies", cooperatives: 5, managers: 9 },
  { region: "Louga", cooperatives: 3, managers: 5 },
  { region: "Casamance", cooperatives: 4, managers: 6 },
  { region: "Saint-Louis", cooperatives: 3, managers: 7 },
  { region: "Kaolack", cooperatives: 3, managers: 4 },
];

export const adminStatusOverview = [
  { label: "Cooperatives actives", value: 14, tone: "success" as BadgeTone },
  { label: "Onboarding en cours", value: 3, tone: "info" as BadgeTone },
  { label: "Cooperatives suspendues", value: 1, tone: "warning" as BadgeTone },
];

export const cooperativeProfile = {
  nom: "Cooperative Deggo Thies",
  code: "COOP-TH-014",
  region: "Thies",
  zone: "Thies Nord et Mbour",
  adresse: "Keur Mame El Hadji, Thies",
  managers: 2,
  membres: 126,
};

export const managerProfile = {
  nom: "Aissatou Ndiaye",
  role: "Manager cooperative",
  email: "a.ndiaye@deggo.sn",
  telephone: "+221 77 445 81 30",
};

export const managerDashboardKpis: StatCard[] = [
  { id: "prod", label: "Production totale", value: 184.6, suffix: " t", trend: "+6,4% vs mars" },
  { id: "perte", label: "Taux de perte", value: 11.8, suffix: "%", trend: "-0,9 pt" },
  { id: "eff", label: "Efficacite", value: 88.2, suffix: "%", trend: "+1,5 pt" },
  { id: "lots", label: "Lots actifs", value: 12, trend: "4 en transformation" },
  { id: "alert", label: "Alertes critiques", value: 2, trend: "Stock mil Grade A" },
];

export const managerTrendSeries = [
  { periode: "S1", production: 28.4, perte: 13.4, efficacite: 84.3 },
  { periode: "S2", production: 30.1, perte: 12.9, efficacite: 85.1 },
  { periode: "S3", production: 29.5, perte: 12.4, efficacite: 86.0 },
  { periode: "S4", production: 31.2, perte: 12.1, efficacite: 86.8 },
  { periode: "S5", production: 32.8, perte: 11.9, efficacite: 87.5 },
  { periode: "S6", production: 32.6, perte: 11.8, efficacite: 88.2 },
];

export const productOverview: ProductOverview[] = [
  {
    produit: "Mangue",
    volumeCollecteTonnes: 74.3,
    stockActuelTonnes: 18.6,
    lotsActifs: 5,
    perteMoyennePct: 9.7,
    gradeA: 64,
    gradeB: 27,
    gradeC: 9,
  },
  {
    produit: "Arachide",
    volumeCollecteTonnes: 62.1,
    stockActuelTonnes: 21.4,
    lotsActifs: 4,
    perteMoyennePct: 11.9,
    gradeA: 48,
    gradeB: 33,
    gradeC: 19,
  },
  {
    produit: "Mil",
    volumeCollecteTonnes: 48.2,
    stockActuelTonnes: 15.8,
    lotsActifs: 3,
    perteMoyennePct: 13.4,
    gradeA: 39,
    gradeB: 37,
    gradeC: 24,
  },
];

export const productComparison = productOverview.map((item) => ({
  produit: item.produit,
  volume: item.volumeCollecteTonnes,
  perte: item.perteMoyennePct,
  efficacite: Number((100 - item.perteMoyennePct).toFixed(1)),
}));

export const members: MemberRecord[] = [
  {
    id: "MBR-001",
    nom: "Awa Diop",
    telephone: "+221 77 612 44 18",
    zone: "Thies Nord",
    culturePrincipale: "Mangue",
    parcelles: 2,
    superficieTotaleHa: 3.8,
    statut: "Actif",
  },
  {
    id: "MBR-002",
    nom: "Moussa Ndour",
    telephone: "+221 70 290 13 77",
    zone: "Mbour",
    culturePrincipale: "Arachide",
    parcelles: 1,
    superficieTotaleHa: 2.1,
    statut: "Actif",
  },
  {
    id: "MBR-003",
    nom: "Fatou Fall",
    telephone: "+221 76 845 31 92",
    zone: "Louga Centre",
    culturePrincipale: "Mil",
    parcelles: 2,
    superficieTotaleHa: 4.5,
    statut: "Saisonnier",
  },
  {
    id: "MBR-004",
    nom: "Ibrahima Ba",
    telephone: "+221 78 430 54 06",
    zone: "Thies Sud",
    culturePrincipale: "Mangue",
    parcelles: 3,
    superficieTotaleHa: 5.2,
    statut: "Actif",
  },
  {
    id: "MBR-005",
    nom: "Khady Seck",
    telephone: "+221 75 331 20 44",
    zone: "Kolda",
    culturePrincipale: "Arachide",
    parcelles: 1,
    superficieTotaleHa: 1.6,
    statut: "Inactif",
  },
  {
    id: "MBR-006",
    nom: "Alioune Kane",
    telephone: "+221 77 541 09 12",
    zone: "Bignona",
    culturePrincipale: "Mil",
    parcelles: 2,
    superficieTotaleHa: 3.1,
    statut: "Actif",
  },
  {
    id: "MBR-007",
    nom: "Penda Mbaye",
    telephone: "+221 70 888 42 33",
    zone: "Mbour",
    culturePrincipale: "Mangue",
    parcelles: 2,
    superficieTotaleHa: 3.4,
    statut: "Actif",
  },
  {
    id: "MBR-008",
    nom: "Seydou Cisse",
    telephone: "+221 76 220 65 01",
    zone: "Louga Ouest",
    culturePrincipale: "Arachide",
    parcelles: 1,
    superficieTotaleHa: 2.7,
    statut: "Saisonnier",
  },
];

export const parcels: ParcelRecord[] = [
  {
    id: "PAR-001",
    code: "TH-ND-021",
    memberId: "MBR-001",
    memberNom: "Awa Diop",
    localisation: "Keur Modou Ndiaye, Thies",
    superficieHa: 1.9,
    typeSol: "Argilo-sableux",
    cultureActuelle: "Mangue",
    statut: "Active",
  },
  {
    id: "PAR-002",
    code: "TH-ND-022",
    memberId: "MBR-001",
    memberNom: "Awa Diop",
    localisation: "Keur Modou Ndiaye, Thies",
    superficieHa: 1.9,
    typeSol: "Sableux",
    cultureActuelle: "Mangue",
    statut: "Preparation",
  },
  {
    id: "PAR-003",
    code: "MB-ND-008",
    memberId: "MBR-002",
    memberNom: "Moussa Ndour",
    localisation: "Darou Salam, Mbour",
    superficieHa: 2.1,
    typeSol: "Argileux",
    cultureActuelle: "Arachide",
    statut: "Active",
  },
  {
    id: "PAR-004",
    code: "LG-FF-014",
    memberId: "MBR-003",
    memberNom: "Fatou Fall",
    localisation: "Ngnith, Louga",
    superficieHa: 2.3,
    typeSol: "Limoneux",
    cultureActuelle: "Mil",
    statut: "Active",
  },
  {
    id: "PAR-005",
    code: "LG-FF-015",
    memberId: "MBR-003",
    memberNom: "Fatou Fall",
    localisation: "Ngnith, Louga",
    superficieHa: 2.2,
    typeSol: "Sableux",
    cultureActuelle: "Mil",
    statut: "Repos",
  },
  {
    id: "PAR-006",
    code: "TH-IB-030",
    memberId: "MBR-004",
    memberNom: "Ibrahima Ba",
    localisation: "Tivaouane, Thies",
    superficieHa: 1.8,
    typeSol: "Argilo-limoneux",
    cultureActuelle: "Mangue",
    statut: "Active",
  },
  {
    id: "PAR-007",
    code: "TH-IB-031",
    memberId: "MBR-004",
    memberNom: "Ibrahima Ba",
    localisation: "Tivaouane, Thies",
    superficieHa: 1.5,
    typeSol: "Sableux",
    cultureActuelle: "Mangue",
    statut: "Preparation",
  },
  {
    id: "PAR-008",
    code: "TH-IB-032",
    memberId: "MBR-004",
    memberNom: "Ibrahima Ba",
    localisation: "Tivaouane, Thies",
    superficieHa: 1.9,
    typeSol: "Argileux",
    cultureActuelle: "Arachide",
    statut: "Active",
  },
  {
    id: "PAR-009",
    code: "CS-AK-011",
    memberId: "MBR-006",
    memberNom: "Alioune Kane",
    localisation: "Oulampane, Casamance",
    superficieHa: 1.4,
    typeSol: "Limoneux",
    cultureActuelle: "Mil",
    statut: "Active",
  },
  {
    id: "PAR-010",
    code: "CS-AK-012",
    memberId: "MBR-006",
    memberNom: "Alioune Kane",
    localisation: "Oulampane, Casamance",
    superficieHa: 1.7,
    typeSol: "Argilo-sableux",
    cultureActuelle: "Mil",
    statut: "Repos",
  },
];

export const inputsHistory: InputRecord[] = [
  {
    id: "INP-260410-01",
    date: "2026-04-10",
    membre: "Awa Diop",
    memberId: "MBR-001",
    produit: "Mangue",
    quantiteKg: 1280,
    grade: "A",
    valeurEstimeeFcfa: 435200,
    statut: "Valide",
  },
  {
    id: "INP-260410-02",
    date: "2026-04-10",
    membre: "Moussa Ndour",
    memberId: "MBR-002",
    produit: "Arachide",
    quantiteKg: 940,
    grade: "B",
    valeurEstimeeFcfa: 225600,
    statut: "Controle qualite",
  },
  {
    id: "INP-260409-03",
    date: "2026-04-09",
    membre: "Fatou Fall",
    memberId: "MBR-003",
    produit: "Mil",
    quantiteKg: 860,
    grade: "B",
    valeurEstimeeFcfa: 154800,
    statut: "Valide",
  },
  {
    id: "INP-260409-04",
    date: "2026-04-09",
    membre: "Ibrahima Ba",
    memberId: "MBR-004",
    produit: "Mangue",
    quantiteKg: 1110,
    grade: "A",
    valeurEstimeeFcfa: 377400,
    statut: "Valide",
  },
  {
    id: "INP-260408-05",
    date: "2026-04-08",
    membre: "Penda Mbaye",
    memberId: "MBR-007",
    produit: "Mangue",
    quantiteKg: 740,
    grade: "C",
    valeurEstimeeFcfa: 170200,
    statut: "En attente",
  },
  {
    id: "INP-260408-06",
    date: "2026-04-08",
    membre: "Seydou Cisse",
    memberId: "MBR-008",
    produit: "Arachide",
    quantiteKg: 690,
    grade: "B",
    valeurEstimeeFcfa: 158700,
    statut: "Valide",
  },
  {
    id: "INP-260407-07",
    date: "2026-04-07",
    membre: "Alioune Kane",
    memberId: "MBR-006",
    produit: "Mil",
    quantiteKg: 920,
    grade: "A",
    valeurEstimeeFcfa: 184000,
    statut: "Valide",
  },
];

export const stockRecords: StockRecord[] = [
  {
    id: "STK-001",
    produit: "Mangue",
    grade: "A",
    quantiteTonnes: 7.2,
    seuilTonnes: 5.5,
    statut: "Correct",
    entrepot: "Depot central Thies",
    derniereMiseAJour: "10 avr 2026, 16:45",
  },
  {
    id: "STK-002",
    produit: "Mangue",
    grade: "B",
    quantiteTonnes: 4.1,
    seuilTonnes: 4.0,
    statut: "A surveiller",
    entrepot: "Depot central Thies",
    derniereMiseAJour: "10 avr 2026, 16:20",
  },
  {
    id: "STK-003",
    produit: "Arachide",
    grade: "A",
    quantiteTonnes: 6.3,
    seuilTonnes: 5.0,
    statut: "Correct",
    entrepot: "Magasin Mbour",
    derniereMiseAJour: "10 avr 2026, 15:58",
  },
  {
    id: "STK-004",
    produit: "Arachide",
    grade: "C",
    quantiteTonnes: 2.3,
    seuilTonnes: 2.8,
    statut: "Critique",
    entrepot: "Magasin Mbour",
    derniereMiseAJour: "10 avr 2026, 14:11",
  },
  {
    id: "STK-005",
    produit: "Mil",
    grade: "A",
    quantiteTonnes: 1.9,
    seuilTonnes: 3.2,
    statut: "Critique",
    entrepot: "Silo Louga",
    derniereMiseAJour: "10 avr 2026, 13:02",
  },
  {
    id: "STK-006",
    produit: "Mil",
    grade: "B",
    quantiteTonnes: 4.5,
    seuilTonnes: 3.8,
    statut: "Correct",
    entrepot: "Silo Louga",
    derniereMiseAJour: "10 avr 2026, 12:50",
  },
];

export const lots: LotRecord[] = [
  {
    id: "LOT-001",
    code: "LT-MG-2604-01",
    produit: "Mangue",
    createdAt: "2026-04-05",
    initialQuantityKg: 3200,
    currentQuantityKg: 2910,
    status: "En transformation",
    progressionPct: 72,
    gradeDominant: "A",
    memberNom: "Awa Diop",
  },
  {
    id: "LOT-002",
    code: "LT-AR-2604-02",
    produit: "Arachide",
    createdAt: "2026-04-06",
    initialQuantityKg: 2850,
    currentQuantityKg: 2490,
    status: "En transformation",
    progressionPct: 61,
    gradeDominant: "B",
    memberNom: "Moussa Ndour",
  },
  {
    id: "LOT-003",
    code: "LT-ML-2604-03",
    produit: "Mil",
    createdAt: "2026-04-07",
    initialQuantityKg: 2600,
    currentQuantityKg: 2210,
    status: "Bloque",
    progressionPct: 44,
    gradeDominant: "B",
    memberNom: "Fatou Fall",
  },
  {
    id: "LOT-004",
    code: "LT-MG-2604-04",
    produit: "Mangue",
    createdAt: "2026-04-08",
    initialQuantityKg: 3100,
    currentQuantityKg: 3100,
    status: "Collecte",
    progressionPct: 16,
    gradeDominant: "A",
    memberNom: "Ibrahima Ba",
  },
  {
    id: "LOT-005",
    code: "LT-AR-2604-05",
    produit: "Arachide",
    createdAt: "2026-04-02",
    initialQuantityKg: 2980,
    currentQuantityKg: 2770,
    status: "Pret",
    progressionPct: 100,
    gradeDominant: "A",
    memberNom: "Seydou Cisse",
  },
  {
    id: "LOT-006",
    code: "LT-MG-2604-06",
    produit: "Mangue",
    createdAt: "2026-04-03",
    initialQuantityKg: 2400,
    currentQuantityKg: 2260,
    status: "Pret",
    progressionPct: 100,
    gradeDominant: "B",
    memberNom: "Penda Mbaye",
  },
];

export const lotStageHistoryByCode: Record<string, LotStageHistory[]> = {
  "LT-MG-2604-01": [
    { stage: "nettoyage", startedAt: "05 avr, 08:20", endedAt: "05 avr, 09:05", state: "termine", rendementPct: 98.3 },
    { stage: "sechage", startedAt: "05 avr, 09:35", endedAt: "05 avr, 16:05", state: "termine", rendementPct: 94.9 },
    { stage: "tri", startedAt: "06 avr, 08:10", endedAt: null, state: "en cours", rendementPct: 91.0 },
    { stage: "emballage", startedAt: "-", endedAt: null, state: "a venir", rendementPct: 0 },
  ],
  "LT-AR-2604-02": [
    { stage: "nettoyage", startedAt: "06 avr, 07:50", endedAt: "06 avr, 08:40", state: "termine", rendementPct: 97.1 },
    { stage: "sechage", startedAt: "06 avr, 09:10", endedAt: null, state: "en cours", rendementPct: 90.8 },
    { stage: "tri", startedAt: "-", endedAt: null, state: "a venir", rendementPct: 0 },
    { stage: "emballage", startedAt: "-", endedAt: null, state: "a venir", rendementPct: 0 },
  ],
  "LT-ML-2604-03": [
    { stage: "nettoyage", startedAt: "07 avr, 08:00", endedAt: "07 avr, 09:00", state: "termine", rendementPct: 96.4 },
    { stage: "sechage", startedAt: "07 avr, 09:30", endedAt: null, state: "en cours", rendementPct: 85.0 },
    { stage: "tri", startedAt: "-", endedAt: null, state: "a venir", rendementPct: 0 },
    { stage: "emballage", startedAt: "-", endedAt: null, state: "a venir", rendementPct: 0 },
  ],
};

export const transformationRecords: TransformationRecord[] = [
  {
    lotCode: "LT-MG-2604-01",
    produit: "Mangue",
    quantiteKg: 2910,
    statut: "En transformation",
    stageActuelle: "tri",
    operateur: "Equipe Tri A",
    historique: lotStageHistoryByCode["LT-MG-2604-01"],
  },
  {
    lotCode: "LT-AR-2604-02",
    produit: "Arachide",
    quantiteKg: 2490,
    statut: "En transformation",
    stageActuelle: "sechage",
    operateur: "Equipe Sechage B",
    historique: lotStageHistoryByCode["LT-AR-2604-02"],
  },
  {
    lotCode: "LT-ML-2604-03",
    produit: "Mil",
    quantiteKg: 2210,
    statut: "Bloque",
    stageActuelle: "sechage",
    operateur: "Equipe Sechage C",
    historique: lotStageHistoryByCode["LT-ML-2604-03"],
  },
];

export const transformationsFlow = [
  { etape: "nettoyage" as StageName, lotsActifs: 3, efficacite: 94.2, perteMoyenne: 2.1 },
  { etape: "sechage" as StageName, lotsActifs: 4, efficacite: 86.3, perteMoyenne: 6.2 },
  { etape: "tri" as StageName, lotsActifs: 3, efficacite: 89.4, perteMoyenne: 4.1 },
  { etape: "emballage" as StageName, lotsActifs: 2, efficacite: 95.1, perteMoyenne: 1.4 },
];

export const lotsToWatch = [
  {
    code: "LT-ML-2604-03",
    produit: "Mil" as ProductName,
    zone: "Louga Centre",
    etape: "sechage" as StageName,
    pertePct: 15.0,
    statut: "Humidite elevee",
    action: "Augmenter ventilation ligne 2",
  },
  {
    code: "LT-AR-2604-02",
    produit: "Arachide" as ProductName,
    zone: "Mbour",
    etape: "sechage" as StageName,
    pertePct: 12.6,
    statut: "A surveiller",
    action: "Reduire duree de cycle",
  },
  {
    code: "LT-MG-2604-01",
    produit: "Mangue" as ProductName,
    zone: "Thies Nord",
    etape: "tri" as StageName,
    pertePct: 9.1,
    statut: "Qualite variable",
    action: "Renforcer controle grade",
  },
];

export const criticalStocks = stockRecords.filter((item) => item.statut !== "Correct");

export const managerQuickActions: QuickAction[] = [
  { label: "Ajouter une collecte", href: "/manager/inputs", tone: "accent" },
  { label: "Creer un lot", href: "/manager/lots" },
  { label: "Lancer une transformation", href: "/manager/transformations" },
  { label: "Verifier les stocks critiques", href: "/manager/stocks" },
];

export const managerRecentActivity: ActivityItem[] = [
  {
    id: "OP-01",
    title: "Collecte mangue validee",
    detail: "Awa Diop - 1 280 kg Grade A",
    date: "10 avr, 16:52",
    tone: "success",
  },
  {
    id: "OP-02",
    title: "Alerte stock mil Grade A",
    detail: "Stock a 1,9 t (seuil 3,2 t)",
    date: "10 avr, 13:02",
    tone: "danger",
  },
  {
    id: "OP-03",
    title: "Lot LT-AR-2604-05 termine",
    detail: "Pret pour expedition interne",
    date: "09 avr, 18:17",
    tone: "info",
  },
  {
    id: "OP-04",
    title: "Controle qualite collecte arachide",
    detail: "Moussa Ndour - Grade B en verification",
    date: "09 avr, 11:40",
    tone: "warning",
  },
];

export const analyticsOverview = [
  { label: "Volume traite", valeur: "143,4 t", tendance: "+8,1%" },
  { label: "Perte globale", valeur: "11,8%", tendance: "-0,9 pt" },
  { label: "Rendement moyen", valeur: "88,2%", tendance: "+1,5 pt" },
  { label: "Lots conformes", valeur: "79%", tendance: "+4 pts" },
];

export const analyticsLossByProduct = [
  { produit: "Mangue" as ProductName, perte: 9.7 },
  { produit: "Arachide" as ProductName, perte: 11.9 },
  { produit: "Mil" as ProductName, perte: 13.4 },
];

export const analyticsEfficiencyByStep = [
  { etape: "nettoyage" as StageName, efficacite: 94.2 },
  { etape: "sechage" as StageName, efficacite: 86.3 },
  { etape: "tri" as StageName, efficacite: 89.4 },
  { etape: "emballage" as StageName, efficacite: 95.1 },
];

export const analyticsLotComparison = [
  { lot: "LT-MG-2604-01", produit: "Mangue" as ProductName, rendement: 90.9, perte: 9.1 },
  { lot: "LT-AR-2604-02", produit: "Arachide" as ProductName, rendement: 87.4, perte: 12.6 },
  { lot: "LT-ML-2604-03", produit: "Mil" as ProductName, rendement: 85.0, perte: 15.0 },
  { lot: "LT-AR-2604-05", produit: "Arachide" as ProductName, rendement: 93.0, perte: 7.0 },
];

export const analyticsVolumeSeries = [
  { semaine: "S1", volume: 21.8 },
  { semaine: "S2", volume: 22.6 },
  { semaine: "S3", volume: 23.1 },
  { semaine: "S4", volume: 24.3 },
  { semaine: "S5", volume: 25.2 },
  { semaine: "S6", volume: 26.4 },
];

export const productFilters: ProductName[] = ["Mangue", "Arachide", "Mil"];

export const gradeFilters: Grade[] = ["A", "B", "C"];

export const managerSidebarLabels = [
  "Tableau de bord",
  "Membres",
  "Parcelles",
  "Produits",
  "Inputs",
  "Stocks",
  "Lots",
  "Transformations",
  "Analytique",
  "Assistant IA",
  "Parametres",
] as const;

export const adminSidebarLabels = ["Tableau de bord", "Cooperatives", "Managers", "Parametres"] as const;

export const assistantSuggestedPrompts = [
  "Quel lot a le plus de pertes cette semaine ?",
  "Montre-moi les stocks critiques",
  "Quel produit a le meilleur rendement ?",
  "Resume les dernieres transformations",
  "Quels membres ont livre le plus ce mois-ci ?",
];

export const assistantMockAnswers: Record<string, { text: string; points: string[] }> = {
  "Quel lot a le plus de pertes cette semaine ?": {
    text: "Le lot LT-ML-2604-03 (Mil) est le plus expose cette semaine.",
    points: [
      "Perte estimee: 15,0%",
      "Etape actuelle: sechage",
      "Action conseillee: augmenter la ventilation ligne 2",
    ],
  },
  "Montre-moi les stocks critiques": {
    text: "Deux stocks sont en niveau critique actuellement.",
    points: [
      "Mil Grade A: 1,9 t (seuil 3,2 t) - Silo Louga",
      "Arachide Grade C: 2,3 t (seuil 2,8 t) - Magasin Mbour",
      "Priorite: reaffecter volumes Mil Grade A",
    ],
  },
  "Quel produit a le meilleur rendement ?": {
    text: "La mangue a le meilleur rendement moyen sur la periode observee.",
    points: [
      "Perte moyenne mangue: 9,7%",
      "Rendement estime: 90,3%",
      "Lots actifs mangue: 5",
    ],
  },
  "Resume les dernieres transformations": {
    text: "Trois lots sont en suivi actif dans le flux post-recolte.",
    points: [
      "LT-MG-2604-01: tri en cours, 2 910 kg",
      "LT-AR-2604-02: sechage en cours, 2 490 kg",
      "LT-ML-2604-03: bloque au sechage, 2 210 kg",
    ],
  },
  "Quels membres ont livre le plus ce mois-ci ?": {
    text: "Les volumes collectes les plus eleves viennent de trois membres.",
    points: [
      "Awa Diop: 1 280 kg",
      "Ibrahima Ba: 1 110 kg",
      "Moussa Ndour: 940 kg",
    ],
  },
};

export const assistantThreads: AssistantThread[] = [
  {
    id: "TH-001",
    title: "Pertes hebdomadaires",
    updatedAt: "Aujourd hui, 17:10",
    preview: "LT-ML-2604-03 reste le plus fragile.",
    messages: [
      {
        id: "TH-001-M1",
        role: "user",
        text: "Quel lot a le plus de pertes cette semaine ?",
        time: "17:08",
      },
      {
        id: "TH-001-M2",
        role: "assistant",
        text: "Le lot LT-ML-2604-03 (Mil) est le plus expose cette semaine.",
        points: ["Perte 15,0%", "Etape: sechage", "Action: ventilation ligne 2"],
        time: "17:09",
      },
    ],
  },
  {
    id: "TH-002",
    title: "Suivi stocks",
    updatedAt: "Aujourd hui, 14:20",
    preview: "2 niveaux critiques a traiter.",
    messages: [
      {
        id: "TH-002-M1",
        role: "user",
        text: "Montre-moi les stocks critiques",
        time: "14:18",
      },
      {
        id: "TH-002-M2",
        role: "assistant",
        text: "Deux stocks sont en niveau critique actuellement.",
        points: ["Mil Grade A: 1,9 t", "Arachide Grade C: 2,3 t", "Priorite sur Mil A"],
        time: "14:19",
      },
    ],
  },
  {
    id: "TH-003",
    title: "Rendement produits",
    updatedAt: "Hier, 18:05",
    preview: "La mangue est en tete.",
    messages: [
      {
        id: "TH-003-M1",
        role: "user",
        text: "Quel produit a le meilleur rendement ?",
        time: "18:04",
      },
      {
        id: "TH-003-M2",
        role: "assistant",
        text: "La mangue affiche le meilleur rendement moyen.",
        points: ["Rendement: 90,3%", "Perte moyenne: 9,7%", "5 lots actifs"],
        time: "18:05",
      },
    ],
  },
];
