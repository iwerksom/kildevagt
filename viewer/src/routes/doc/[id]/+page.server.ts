import { error } from "@sveltejs/kit";
import { getDocument } from "#lib/server/data.ts";
import { fromId } from "#lib/id.ts";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ params }) => {
  const doc = await getDocument(fromId(params.id));
  if (!doc) error(404, "Document not found");
  return { doc };
};
