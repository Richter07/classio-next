import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "./api/client";

export type Role = "DIRECTOR" | "CENSOR" | "SECRETARY" | "TEACHER";
export type School = { id: string; name: string; slug: string; color_primary: string; color_accent: string };
export type Me = { phone: string; is_parent: boolean; school: School | null; roles: Role[]; full_name: string };

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api<Me>("auth/me/");
      } catch (error) {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
        throw error;
      }
    },
    staleTime: 60_000,
    retry: false,
  });
}

export function useLogout() {
  const client = useQueryClient();
  return async () => {
    await api("auth/logout/", { method: "POST" }).catch(() => undefined);
    client.clear();
  };
}

export const isDirection = (me: Me) => me.roles.includes("DIRECTOR") || me.roles.includes("CENSOR");
export const isOffice = (me: Me) => me.roles.includes("SECRETARY") || me.roles.includes("DIRECTOR");
export const isTeacher = (me: Me) => me.roles.includes("TEACHER");
