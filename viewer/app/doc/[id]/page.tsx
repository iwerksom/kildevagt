import { notFound } from "next/navigation";
import Viewer from "@/components/Viewer";
import { fromId, getDocument } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const doc = await getDocument(fromId(id));
  if (!doc) notFound();
  return <Viewer doc={doc} />;
}
