// Serves the static export (`out/`) the way Amplify does: `/app/` is `app/index.html`.
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";

const root = join(import.meta.dirname, "..", "out");
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".txt": "text/plain",
  ".ico": "image/x-icon", ".woff2": "font/woff2", ".svg": "image/svg+xml", ".json": "application/json" };

createServer((request, response) => {
  const path = normalize(decodeURIComponent(new URL(request.url, "http://x").pathname)).replace(/^[\\/]+/, "");
  let file = join(root, path);
  if (!file.startsWith(root)) return response.writeHead(403).end();
  if (existsSync(file) && statSync(file).isDirectory()) file = join(file, "index.html");
  if (!existsSync(file)) file = join(root, "404.html");
  response.writeHead(file.endsWith("404.html") ? 404 : 200, { "content-type": types[extname(file)] ?? "application/octet-stream" });
  createReadStream(file).pipe(response);
}).listen(4173, "127.0.0.1");
