import { api } from "./api";
import type { SystemHealth } from "../types/system";

export async function getSystemHealth(): Promise<SystemHealth> {
  const response = await api.get<SystemHealth>("/api/system/health");
  return response.data;
}
