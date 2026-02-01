export interface LocationInfo {
  country: string;
  countryName: string;
  lat: number;
  lng: number;
}

export interface Metrics {
  searches: number;
  y: number;
  slope: number;
  accel: number;
  level_z: number;
  accel_z: number;
}

export interface SocialPost {
  id: string;
  content: string;
  originalText: string;
  author: string;
  timestamp: string;
  sentiment: string;
  sentimentScore: number;
  keywords: string[];
}

export interface Alert {
  id: string;
  timestamp?: string;
  timeAgo?: string;
  location?: LocationInfo;
  product?: string;
  severity?: "EARLY" | "CONFIRMED";
  severityLevel?: "CRITICAL" | "HIGH" | "ELEVATED" | "WATCH" | "NORMAL";
  severityScore?: number;
  severityColor?: string;
  metrics?: Metrics;
  socialPosts?: SocialPost[];
}

export interface GetAlertsResponse {
  count: number;
  alerts: Alert[];
}