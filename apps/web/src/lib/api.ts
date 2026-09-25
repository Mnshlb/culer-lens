import { useQuery } from "@tanstack/react-query";
import type { components } from "./api-schema";

export type Schemas = components["schemas"];
export type MatchSummary = Schemas["MatchSummary"];
export type MatchDetail = Schemas["MatchDetail"];
export type Overview = Schemas["Overview"];
export type PredictionOut = Schemas["PredictionOut"];
export type LineupOut = Schemas["LineupOut"];
export type LineupPlayer = Schemas["LineupPlayer"];
export type Shot = Schemas["Shot"];
export type PassNetwork = Schemas["PassNetwork"];
export type PlayerListItem = Schemas["PlayerListItem"];
export type PlayerProfile = Schemas["PlayerProfile"];
export type PlayerMatchRow = Schemas["PlayerMatchRow"];
export type Heatmap = Schemas["Heatmap"];
export type Workload = Schemas["Workload"];
export type ModelSummary = Schemas["ModelSummary"];

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function get<T>(path: string, params?: Record<string, string | number | undefined | null>): Promise<T> {
  const url = new URL(API_URL + path);
  Object.entries(params ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  });
  const res = await fetch(url.toString());
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const useApi = <T,>(key: unknown[], path: string, params?: Record<string, string | number | undefined | null>, enabled = true) =>
  useQuery<T, ApiError>({ queryKey: key, queryFn: () => get<T>(path, params), enabled });

export const useSeasons = () => useApi<{ label: string; start_year: number }[]>(["seasons"], "/api/seasons");
export const useOverview = (asOf?: string) => useApi<Overview>(["overview", asOf], "/api/overview", { as_of: asOf });
export const useMatches = (season?: string) => useApi<MatchSummary[]>(["matches", season], "/api/matches", { season });
export const useMatch = (id: number) => useApi<MatchDetail>(["match", id], `/api/matches/${id}`);
export const useShots = (id: number, enabled = true) => useApi<Shot[]>(["shots", id], `/api/matches/${id}/shots`, undefined, enabled);
export const usePasses = (id: number, enabled = true) =>
  useApi<PassNetwork>(["passes", id], `/api/matches/${id}/passes`, undefined, enabled);
export const usePlayers = (season?: string, minMinutes = 0) =>
  useApi<PlayerListItem[]>(["players", season, minMinutes], "/api/players", { season, min_minutes: minMinutes });
export const usePlayer = (id: number) => useApi<PlayerProfile>(["player", id], `/api/players/${id}`);
export const usePlayerStats = (id: number, season?: string) =>
  useApi<PlayerMatchRow[]>(["player-stats", id, season], `/api/players/${id}/stats`, { season });
export const useHeatmap = (
  id: number,
  p: { family: string; window: string; season?: string; match_id?: number; as_of?: string },
) => useApi<Heatmap>(["heatmap", id, p], `/api/players/${id}/heatmap`, p);
export const useWorkload = (id: number, season?: string) =>
  useApi<Workload>(["workload", id, season], `/api/players/${id}/workload`, { season });
export const useModels = () => useApi<ModelSummary[]>(["models"], "/api/models");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const useModel = (id: number) => useApi<any>(["model", id], `/api/models/${id}`);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const useModelExplanation = (id: number) => useApi<any>(["model-exp", id], `/api/models/${id}/explanation`);
export const useTeamForm = (teamId: number | undefined, asOf?: string) =>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  useApi<any>(["team-form", teamId, asOf], `/api/teams/${teamId}/form`, { as_of: asOf, n: 60 }, teamId !== undefined);
