export type BadgeTone = "success" | "warning" | "danger" | "neutral" | "info" | "ai";

export type ActivityItem = {
  id: string;
  title: string;
  detail: string;
  date: string;
  tone: BadgeTone;
};

export type QuickAction = {
  label: string;
  href: string;
  tone?: "default" | "accent";
};

export type TrendPoint = {
  period: string;
  production: number;
  loss: number;
  efficiency: number;
};

export type ProductComparisonPoint = {
  product: string;
  volume: number;
  loss: number;
  efficiency: number;
};
