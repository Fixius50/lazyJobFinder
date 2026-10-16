export interface ActiveCVInfo {
  type: "canonical" | "custom" | "none";
  filename: string;
  path: string;
  size_bytes: number;
  modified_at: string;
  is_default: boolean;
  description: string;
}
