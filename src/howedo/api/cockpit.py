from __future__ import annotations

COCKPIT_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>HOWEDO · Continuity Cockpit</title>
  <style>
    :root {
      --bg: #070b10;
      --panel: rgba(12, 20, 29, 0.78);
      --line: rgba(130, 255, 211, 0.16);
      --text: #e8fff7;
      --muted: #8fa9a0;
      --accent: #78ffd6;
      --accent2: #8db8ff;
      --warn: #ffcf78;
      --danger: #ff7d92;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 0%, rgba(120,255,214,.12), transparent 32rem),
        radial-gradient(circle at 88% 12%, rgba(141,184,255,.10), transparent 28rem),
        linear-gradient(180deg, #081019 0%, var(--bg) 54%, #05070a 100%);
      font: 15px/1.55 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .shell { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 56px; }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 32px;
    }
    .brand { font-weight: 800; letter-spacing: .22em; }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--warn);
      box-shadow: 0 0 18px currentColor;
    }
    .dot.ok { background: var(--accent); }
    .hero {
      padding: clamp(28px, 5vw, 64px);
      border: 1px solid var(--line);
      border-radius: 28px;
      background: linear-gradient(135deg, rgba(18,31,42,.88), rgba(8,13,19,.78));
      box-shadow: 0 30px 100px rgba(0,0,0,.35);
      overflow: hidden;
      position: relative;
    }
    .hero::after {
      content: "";
      position: absolute;
      inset: auto -10% -55% 20%;
      height: 70%;
      background: radial-gradient(ellipse, rgba(120,255,214,.12), transparent 68%);
      pointer-events: none;
    }
    .eyebrow { color: var(--accent); letter-spacing: .14em; text-transform: uppercase; }
    h1 {
      margin: 12px 0 14px;
      max-width: 880px;
      font: 800 clamp(36px, 7vw, 74px)/.98 ui-sans-serif, system-ui, sans-serif;
      letter-spacing: -.055em;
    }
    .lede {
      max-width: 790px;
      margin: 0;
      color: #bad0c8;
      font-size: clamp(16px, 2vw, 20px);
    }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px; }
    button, .button {
      appearance: none;
      border: 1px solid rgba(120,255,214,.28);
      border-radius: 12px;
      padding: 11px 15px;
      color: #03110d;
      background: var(--accent);
      cursor: pointer;
      font: inherit;
      font-weight: 800;
    }
    .button.secondary {
      color: var(--text);
      background: rgba(255,255,255,.035);
      border-color: rgba(255,255,255,.12);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 16px;
      margin-top: 16px;
    }
    .card {
      grid-column: span 4;
      min-height: 172px;
      padding: 20px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--panel);
      backdrop-filter: blur(16px);
    }
    .wide { grid-column: span 8; }
    .full { grid-column: 1 / -1; }
    .label {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    .metric { font-size: 26px; font-weight: 800; }
    .decisions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
    .decision {
      border: 1px solid rgba(255,255,255,.10);
      border-radius: 999px;
      padding: 6px 10px;
      color: #bfd4cd;
      background: rgba(255,255,255,.025);
    }
    .decision.primary { color: var(--accent); border-color: rgba(120,255,214,.22); }
    .flow {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 8px;
      margin-top: 18px;
    }
    .flow div {
      min-height: 78px;
      padding: 12px;
      border-radius: 12px;
      border: 1px solid rgba(255,255,255,.08);
      background: rgba(255,255,255,.025);
    }
    .flow strong { display: block; color: var(--accent); margin-bottom: 4px; }
    pre {
      margin: 12px 0 0;
      min-height: 220px;
      max-height: 430px;
      overflow: auto;
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 12px;
      padding: 15px;
      color: #c9ded6;
      background: #05080b;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .small { color: var(--muted); font-size: 13px; }
    footer { padding-top: 30px; color: var(--muted); text-align: center; }
    @media (max-width: 820px) {
      .card, .wide { grid-column: 1 / -1; }
      .flow { grid-template-columns: 1fr; }
      .topbar { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">HOWEDO</div>
      <div class="status"><span id="health-dot" class="dot"></span><span id="health">checking runtime</span></div>
    </header>

    <section class="hero">
      <div class="eyebrow">Continuity control plane · R16.3</div>
      <h1>Know when an AI agent must not continue.</h1>
      <p class="lede">
        HOWEDO validates whether the state, dependencies, semantics, fences, and recovery
        assumptions behind an execution are still valid before the execution proceeds.
      </p>
      <div class="actions">
        <button id="run-demo" type="button">Run continuity proof</button>
        <a class="button secondary" href="/docs">Open API docs</a>
        <a class="button secondary" href="/openapi.json">OpenAPI JSON</a>
      </div>
    </section>

    <section class="grid" aria-label="HOWEDO system overview">
      <article class="card">
        <div class="label">Runtime boundary</div>
        <div class="metric">Fail closed</div>
        <p class="small">Unverifiable or stale execution assumptions do not silently become valid.</p>
      </article>
      <article class="card">
        <div class="label">Evidence</div>
        <div class="metric">Witnessed</div>
        <p class="small">Every continuity decision can carry deterministic, reproducible evidence.</p>
      </article>
      <article class="card">
        <div class="label">Integration model</div>
        <div class="metric">Vendor-neutral</div>
        <p class="small">The kernel stays independent from the agent runtime and persistence vendor.</p>
      </article>

      <article class="card full">
        <div class="label">Decision contract</div>
        <div class="decisions">
          <span class="decision primary">CONTINUE</span>
          <span class="decision">PAUSE</span>
          <span class="decision">REVALIDATE</span>
          <span class="decision">ABORT</span>
          <span class="decision primary">RECOVER</span>
        </div>
      </article>

      <article class="card wide">
        <div class="label">Continuity pipeline</div>
        <div class="flow">
          <div><strong>STATE</strong>Exact identities and revisions</div>
          <div><strong>SEMLOCK</strong>Semantic compatibility</div>
          <div><strong>RECALL</strong>Dependency invalidation</div>
          <div><strong>CONCUR</strong>Heads, fences, conflicts</div>
          <div><strong>DECIDE</strong>Action + witness</div>
        </div>
      </article>

      <article class="card">
        <div class="label">Operator endpoints</div>
        <p><a href="/health">/health</a><br><a href="/ready">/ready</a><br><a href="/docs">/docs</a></p>
        <p class="small">The cockpit is presentation only. Continuity semantics remain in the kernel.</p>
      </article>

      <article class="card full">
        <div class="label">Live proof output</div>
        <div class="small">
          The demo posts an exact-state snapshot to <code>/v1/continuity/check</code>.
        </div>
        <pre id="output">Press “Run continuity proof” to execute a real API decision.</pre>
      </article>
    </section>

    <footer>
      Persistence tells you what the agent knew. HOWEDO determines whether it is still valid to act on it.
    </footer>
  </main>

  <script>
    const output = document.getElementById("output");
    const health = document.getElementById("health");
    const healthDot = document.getElementById("health-dot");

    async function refreshHealth() {
      try {
        const response = await fetch("/health", {headers: {"Accept": "application/json"}});
        const body = await response.json();
        if (!response.ok) throw new Error("health endpoint returned " + response.status);
        health.textContent = body.service + " · " + body.status;
        healthDot.classList.add("ok");
      } catch (error) {
        health.textContent = "runtime unavailable";
        healthDot.classList.remove("ok");
      }
    }

    async function runDemo() {
      const resource = {
        resource_id: "repo://howedo/demo",
        revision: "git:canonical",
        digest: "sha256:demo"
      };
      output.textContent = "running…";
      try {
        const response = await fetch("/v1/continuity/check", {
          method: "POST",
          headers: {"Content-Type": "application/json", "Accept": "application/json"},
          body: JSON.stringify({snapshot: [resource], current_heads: [resource]})
        });
        const body = await response.json();
        output.textContent = JSON.stringify(body, null, 2);
      } catch (error) {
        output.textContent = "request failed: " + error;
      }
    }

    document.getElementById("run-demo").addEventListener("click", runDemo);
    refreshHealth();
  </script>
</body>
</html>
"""


def render_cockpit() -> str:
    return COCKPIT_HTML
