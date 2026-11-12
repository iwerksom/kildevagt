import adapter from "@sveltejs/adapter-node";
import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  // Make .env.local (NEO4J_PASSWORD) visible to server code as process.env during dev and build.
  // `npm start` loads the same file with node --env-file.
  Object.assign(process.env, loadEnv(mode, process.cwd(), ""));
  return { plugins: [sveltekit({ adapter: adapter() })] };
});
