import { query } from "gitclaw";

function parseArgs(argv) {
  const args = {};

  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    const value = argv[index + 1];

    if (!key.startsWith("--")) {
      continue;
    }

    if (value === undefined || value.startsWith("--")) {
      args[key.slice(2)] = "";
      continue;
    }

    args[key.slice(2)] = value;
    index += 1;
  }

  return args;
}

function eventFromMessage(message) {
  const base = {
    type: message.type ?? "unknown",
  };

  if (message.type === "assistant") {
    return {
      ...base,
      content: message.content ?? "",
      model: message.model,
      stopReason: message.stopReason,
      usage: message.usage,
    };
  }

  if (message.type === "tool_use") {
    return {
      ...base,
      toolName: message.toolName,
      args: message.args,
      toolCallId: message.toolCallId,
    };
  }

  if (message.type === "tool_result") {
    return {
      ...base,
      content: message.content ?? "",
      isError: message.isError ?? false,
      toolCallId: message.toolCallId,
    };
  }

  if (message.type === "system") {
    return {
      ...base,
      subtype: message.subtype,
      content: message.content ?? "",
      metadata: message.metadata,
    };
  }

  if (message.type === "delta") {
    return {
      ...base,
      deltaType: message.deltaType,
      content: message.content ?? "",
    };
  }

  return {
    ...base,
    content: message.content ?? "",
  };
}

function compactEvents(events) {
  return events.filter((event) => event.type !== "delta");
}

const args = parseArgs(process.argv.slice(2));
const repoPath = args.repoPath;
const prompt = args.prompt;
const model = args.model;

if (!repoPath || !prompt || !model) {
  console.log(
    JSON.stringify({
      status: "error",
      error:
        "Missing required arguments. Expected --repoPath <path> --prompt <prompt> --model <model>.",
      events: [],
    }),
  );
  process.exit(2);
}

const events = [];
const startedAt = new Date().toISOString();

try {
  for await (const message of query({
    dir: repoPath,
    prompt,
    model,
    disallowedTools: ["cli"],
    maxTurns: 30,
  })) {
    events.push(eventFromMessage(message));
  }

  console.log(
    JSON.stringify({
      status: "completed",
      error: "",
      startedAt,
      completedAt: new Date().toISOString(),
      events: compactEvents(events),
    }),
  );
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);

  console.log(
    JSON.stringify({
      status: "error",
      error: message,
      startedAt,
      completedAt: new Date().toISOString(),
      events: compactEvents(events),
    }),
  );
  process.exit(1);
}
