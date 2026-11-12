// Production start, same on Linux and Windows: bind to localhost only, load .env.local, run the built server.
import { existsSync } from "node:fs";

process.env.HOST ??= "127.0.0.1";
process.env.PORT ??= "3000";
if (existsSync(".env.local")) process.loadEnvFile(".env.local");

await import("./build/index.js");
