export type DocumentRow = {
  url: string; title: string; source: string; date: string | null;
  change: string; fetchedAt: string; items: number; mentions: number;
};

export type Mention = {
  item: string; snippet: string; method: string; confidence: number;
  sourceUrl: string; fetchedAt: string; sha256: string;
};

export type Entity = {
  key: string; kind: "Company" | "Organisation" | "Unclassified" | "Person" | "Place"; name: string;
  verified: boolean; mentions: Mention[]; alsoIn: { title: string; source: string; url: string }[];
};

export type DocumentDetail = {
  url: string; title: string; source: string; date: string | null; sha256: string; fetchedAt: string;
  items: { number: string; title: string }[]; entities: Entity[];
};
