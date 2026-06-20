import fs from "node:fs/promises";
import { existsSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ASSETS_DIR = path.join(ROOT, "docs", "assets");
const PROFILE_DIR = path.join(ROOT, ".tmp-streamlit-chrome-profile");
const URL = process.argv[2] ?? "http://127.0.0.1:8501/?embed=true";
const PORT = 9300 + Math.floor(Math.random() * 500);
const WIDTH = 1600;
const HEIGHT = 1100;

const captures = [
  {
    tab: "City Overview",
    output: "sf-city-pulse-streamlit.png",
    markers: ["Total 311 requests", "Monthly activity trend"],
    minPlots: 2,
  },
  {
    tab: "District Equity",
    output: "sf-city-pulse-streamlit-district-equity.png",
    markers: ["District detail", "District response time index"],
    minPlots: 2,
  },
  {
    tab: "Construction vs Complaints",
    output: "sf-city-pulse-streamlit-construction.png",
    markers: ["Minimum 311 requests for rankings", "Construction activity versus 311 complaints"],
    minPlots: 1,
  },
  {
    tab: "Neighborhood Drilldown",
    output: "sf-city-pulse-streamlit-neighborhood.png",
    markers: ["Neighborhood", "Mission monthly profile"],
    minPlots: 1,
  },
];

const browserCandidates = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
];

function getBrowserPath() {
  const found = browserCandidates.find((candidate) => existsSync(candidate));
  if (!found) {
    throw new Error("Could not find Chrome or Edge.");
  }
  return found;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getJson(url) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        body += chunk;
      });
      response.on("end", () => {
        try {
          resolve(JSON.parse(body));
        } catch (error) {
          reject(error);
        }
      });
    });
    request.on("error", reject);
    request.setTimeout(2000, () => {
      request.destroy(new Error(`Timed out fetching ${url}`));
    });
  });
}

async function waitForPageTarget() {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const targets = await getJson(`http://127.0.0.1:${PORT}/json/list`);
      const page = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
      if (page) return page;
    } catch {
      // Chrome is still starting.
    }
    await sleep(250);
  }
  throw new Error("Chrome DevTools target did not become available.");
}

async function connect(webSocketDebuggerUrl) {
  const ws = new WebSocket(webSocketDebuggerUrl);
  ws.binaryType = "arraybuffer";
  const pending = new Map();
  const events = [];
  let id = 0;

  ws.addEventListener("message", async (event) => {
    const payload = typeof event.data === "string"
      ? event.data
      : Buffer.from(event.data).toString("utf8");
    const message = JSON.parse(payload);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
      return;
    }
    events.push(message);
  });

  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });

  function send(method, params = {}) {
    const messageId = ++id;
    ws.send(JSON.stringify({ id: messageId, method, params }));
    return new Promise((resolve, reject) => {
      pending.set(messageId, { resolve, reject });
      setTimeout(() => {
        if (pending.has(messageId)) {
          pending.delete(messageId);
          reject(new Error(`${method} timed out`));
        }
      }, 15000);
    });
  }

  return { ws, send, events };
}

async function waitForStreamlitContent(client, markers, minPlots = 1) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const result = await client.send("Runtime.evaluate", {
      expression: `(() => {
        const text = document.body ? document.body.innerText : '';
        const plotlyCount = document.querySelectorAll('.js-plotly-plot').length;
        const svgCount = document.querySelectorAll('.js-plotly-plot svg').length;
        return { text, plotlyCount, svgCount };
      })()`,
      returnByValue: true,
    });
    const page = result.result?.value ?? {};
    const text = page.text ?? "";
    const hasMarkers = markers.every((marker) => text.includes(marker));
    const renderedPlots = Math.max(page.plotlyCount ?? 0, page.svgCount ?? 0);
    if (hasMarkers && renderedPlots >= minPlots) {
      await sleep(5000);
      return;
    }
    await sleep(500);
  }
  await sleep(8000);
}

async function clickTab(client, tabName) {
  const result = await client.send("Runtime.evaluate", {
    expression: `(() => {
      const tabName = ${JSON.stringify(tabName)};
      const tabs = [...document.querySelectorAll('[role="tab"], button')];
      const tab = tabs.find((element) => (element.innerText || '').trim().includes(tabName));
      if (!tab) return false;
      tab.click();
      window.scrollTo(0, 0);
      return true;
    })()`,
    returnByValue: true,
  });
  if (!result.result?.value) {
    throw new Error(`Could not find Streamlit tab: ${tabName}`);
  }
}

async function captureViewport(client, outputPath) {
  await client.send("Runtime.evaluate", {
    expression: "window.scrollTo(0, 0)",
    returnByValue: true,
  });
  await sleep(1000);
  const screenshot = await client.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  await fs.writeFile(outputPath, Buffer.from(screenshot.data, "base64"));
  console.log(outputPath);
}

async function main() {
  await fs.mkdir(ASSETS_DIR, { recursive: true });
  await fs.rm(PROFILE_DIR, { recursive: true, force: true });
  await fs.mkdir(PROFILE_DIR, { recursive: true });

  const browser = spawn(getBrowserPath(), [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-allow-origins=*",
    `--user-data-dir=${PROFILE_DIR}`,
    `--remote-debugging-port=${PORT}`,
    `--window-size=${WIDTH},${HEIGHT}`,
    URL,
  ], {
    stdio: "ignore",
    windowsHide: true,
  });

  try {
    const target = await waitForPageTarget();
    const websocketUrl = target.webSocketDebuggerUrl.replace("ws://localhost", "ws://127.0.0.1");
    const client = await connect(websocketUrl);
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await client.send("Emulation.setDeviceMetricsOverride", {
      width: WIDTH,
      height: HEIGHT,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await client.send("Page.navigate", { url: URL });
    await waitForStreamlitContent(client, captures[0].markers, captures[0].minPlots);

    for (const capture of captures) {
      await clickTab(client, capture.tab);
      await waitForStreamlitContent(client, capture.markers, capture.minPlots);
      await captureViewport(client, path.join(ASSETS_DIR, capture.output));
    }

    client.ws.close();
  } finally {
    browser.kill();
    try {
      await fs.rm(PROFILE_DIR, { recursive: true, force: true });
    } catch {
      // Chrome can keep Crashpad files locked briefly after the screenshot is written.
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
