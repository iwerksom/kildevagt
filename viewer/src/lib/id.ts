// Document URLs contain ?, & and /, so they travel in routes as base64url. Works in browser and server.
export const toId = (url: string) => {
  const bytes = new TextEncoder().encode(url);
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};

export const fromId = (id: string) => {
  const padded = id.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(id.length / 4) * 4, "=");
  const binary = atob(padded);
  return new TextDecoder().decode(Uint8Array.from(binary, (c) => c.charCodeAt(0)));
};
