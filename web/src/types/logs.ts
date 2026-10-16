export interface SystemLogItem {
  id: number;
  timestamp: string;
  level: "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  source: string;
  message: string;
  details?: string;
}
