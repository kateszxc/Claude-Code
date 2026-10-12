export type Option = { id: string; label: string };

export type Options = {
  niches: Option[];
  revenue_bands: Option[];
  funding: Option[];
  providers: { search: "brave" | "serpapi" | "duckduckgo"; hunter: boolean; ai: boolean };
};

export type ScrapeRequest = {
  count: number;
  niche: string;
  keywords: string;
  country: string;
  revenue_bands: string[];
  min_age_years: number | null;
  max_age_years: number | null;
  funding: string;
  seed_urls: string[];
  strict_filters: boolean;
  use_ai: boolean;
};

export type BrandResult = {
  brand_name: string;
  domain: string;
  website_url: string;
  niche: string;
  what_they_do: string;
  platform: string;
  founder_name: string;
  founder_email: string;
  email_confidence: "verified" | "high" | "medium" | "low" | "none" | string;
  email_source: string;
  other_emails: string[];
  est_revenue_band: string;
  revenue_basis: string;
  brand_age_years: number | null;
  founded_year: number | null;
  age_source: string;
  funding_status: string;
  funding_details: string;
  product_count: string;
  price_range: string;
  avg_price: number | null;
  socials: Record<string, string>;
  marketing_stack: string[];
  marketing_score: number;
  website_improvements: string[];
  marketing_improvements: string[];
  brand_improvements: string[];
  filter_notes: string[];
};

export type Job = {
  id: string;
  status: "queued" | "running" | "done" | "cancelled" | "error";
  request: ScrapeRequest;
  found: number;
  scanned: number;
  candidates: number;
  message: string;
  logs: string[];
  results: BrandResult[];
  csv_path: string;
};
