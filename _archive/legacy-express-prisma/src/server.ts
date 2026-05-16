import "dotenv/config";
import { createServer } from "node:http";
import { createApp } from "./app";
import { initSocket } from "./socket/io";

const app = createApp();
const server = createServer(app);
initSocket(server);

const port = Number(process.env.PORT || 8000);

server.listen(port, () => {
  process.stdout.write(`WeeFarm API running on :${port}\n`);
});
