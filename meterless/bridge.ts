// JSON-lines bridge to Meterless H-MEM. One request per line on stdin, one response per line on stdout.
//   {"id":1,"op":"remember","content":"...","source":"stockwhy:case"}
//   {"id":2,"op":"recall","query":"...","topN":8}
//   {"id":3,"op":"feedback","memoryId":"mem-1","kind":"helpful"}      kind: helpful | not_helpful | wrong
//   {"id":4,"op":"audit","memoryId":"mem-1"}
import readline from "node:readline";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { HMEM } from "./hmem/src/index.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const persistDir = process.env.MEMORY_DIR ?? path.join(here, "..", ".meterless_state");
const hmem: any = new HMEM({ persistDir });

function send(obj: unknown): void {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

const rl = readline.createInterface({ input: process.stdin });
rl.on("line", (line: string) => {
  let req: any = {};
  try {
    req = JSON.parse(line);
    switch (req.op) {
      case "ping":
        send({ id: req.id, ok: true, engine: "H-MEM (Meterless reference)", persistDir });
        break;
      case "remember": {
        const rec = hmem.add({ content: req.content, type: "general", source: req.source ?? "stockwhy", tags: req.tags ?? [] });
        send({ id: req.id, ok: true, memoryId: rec.id, layer: rec.layer });
        break;
      }
      case "recall": {
        const res = hmem.query(req.query, { topN: req.topN ?? 8, threshold: req.threshold ?? 0.05 });
        send({
          id: req.id,
          ok: true,
          memories: res.memories.map((m: any) => ({ id: m.memory.id, relevance: m.relevance, content: m.memory.content })),
          strategy: res.trace?.strategy,
        });
        break;
      }
      case "feedback":
        hmem.feedback(req.memoryId, req.kind);
        send({ id: req.id, ok: true });
        break;
      case "audit":
        send({
          id: req.id,
          ok: true,
          history: hmem.ledger.history(req.memoryId).map((e: any) => ({ action: e.action, actor: e.actor, at: e.timestamp, confidence: e.newState?.confidence })),
        });
        break;
      default:
        send({ id: req.id, ok: false, error: `unknown op ${req.op}` });
    }
  } catch (err) {
    send({ id: req.id, ok: false, error: String((err as Error).message ?? err) });
  }
});
