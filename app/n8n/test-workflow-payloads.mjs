import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const root = new URL("./", import.meta.url);

function loadWorkflow(file) {
  return JSON.parse(readFileSync(new URL(file, root), "utf8"));
}

function node(workflow, name) {
  const found = workflow.nodes.find((candidate) => candidate.name === name);
  assert.ok(found, "missing node: " + name);
  return found;
}

function runPrepareBody(
  workflow,
  webhookName,
  body,
  expectedKey = "x".repeat(32),
  sentKey = expectedKey,
) {
  const code = node(workflow, "Prepare Body").parameters.jsCode;
  const sandbox = {
    $: () => ({
      item: {
        json: {
          body,
          headers: { "x-ness-webhook-key": sentKey },
        },
      },
    }),
    $env: { NINF_N8N_WEBHOOK_API_KEY: expectedKey },
  };
  return runInNewContext(["(() => {", code, "})()"].join("\n"), sandbox);
}

const incident = loadWorkflow("workflow_incident_created.json");
const incidentBody = {
  event_name: "Alert\r\nBcc: attacker@example.test",
  customer_name: "<img src=x onerror=\"alert(1)\">&",
  host_name: "edge-01",
  severity_label: "HIGH",
  fingerprint: "fp-1",
  clean_payload: { description: "<script>alert('x')</script>" },
};
const incidentOutput = runPrepareBody(incident, "Webhook", incidentBody);
assert.match(incidentOutput.emailHtml, /&lt;img/);
assert.match(incidentOutput.emailHtml, /&amp;/);
assert.doesNotMatch(incidentOutput.emailHtml, /<img|<script/i);
assert.doesNotMatch(incidentOutput.emailSubject, /[\r\n]/);
assert.equal(Object.hasOwn(incidentOutput, "number"), false);
assert.throws(
  () => runPrepareBody(incident, "Webhook", incidentBody, "x".repeat(32), "wrong"),
  /Unauthorized webhook request/,
);
assert.throws(
  () => runPrepareBody(incident, "Webhook", null),
  /Invalid incident payload/,
);
assert.equal(node(incident, "Send Email (Abrir Chamado)").onError, undefined);

const postmortem = loadWorkflow("workflow_postmortem_ready.json");
const postmortemBody = {
  customer_name: "Acme",
  summary: "<svg onload=\"alert(1)\">summary</svg>",
  root_cause: "x < y & z",
  corrective_actions: ["</p><img src=x onerror=alert(1)>", "restart service"],
  blast_radius: "one",
};
const postmortemOutput = runPrepareBody(
  postmortem,
  "Webhook-PostMortem",
  postmortemBody,
);
assert.match(postmortemOutput.emailHtml, /&lt;svg/);
assert.match(postmortemOutput.emailHtml, /&lt;img/);
assert.doesNotMatch(postmortemOutput.emailHtml, /<svg|<img/i);
assert.doesNotMatch(postmortemOutput.emailSubject, /[\r\n]/);
assert.equal(Object.hasOwn(postmortemOutput, "number"), false);
assert.throws(
  () =>
    runPrepareBody(
      postmortem,
      "Webhook-PostMortem",
      postmortemBody,
      "x".repeat(32),
      "wrong",
    ),
  /Unauthorized webhook request/,
);
assert.throws(
  () => runPrepareBody(postmortem, "Webhook-PostMortem", []),
  /Invalid postmortem payload/,
);
assert.equal(node(postmortem, "Send Email (Enviar PostMortem)").onError, undefined);

for (const [workflow, whatsappName] of [
  [incident, "WhatsApp - Notificar Grupo"],
  [postmortem, "WhatsApp - PostMortem Grupo"],
]) {
  const whatsapp = node(workflow, whatsappName);
  assert.doesNotMatch(JSON.stringify(whatsapp.parameters), /changeme|group-id/);
}

console.log("n8n workflow payload safety: PASS");
