import { listDocuments } from "#lib/server/data.ts";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async () => {
  try {
    return { docs: await listDocuments(), error: null };
  } catch (error) {
    return { docs: [], error: String(error) };
  }
};
