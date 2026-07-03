import { chromium } from "playwright";
import { mkdir } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "../docs/assignment-figures");
const baseUrl = "https://safir-hyouka.vercel.app";

async function waitForApp(page) {
  await page.goto(baseUrl, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForSelector(".demo-banner", { timeout: 60000 });
  await page.waitForTimeout(1500);
}

async function switchRole(page, employeeId) {
  const select = page.locator(".demo-role-switcher-select");
  await select.waitFor({ timeout: 30000 });
  await select.selectOption(employeeId);
  await page.waitForTimeout(2500);
}

async function capture(page, name) {
  await page.screenshot({
    path: path.join(outDir, `${name}.png`),
    fullPage: false,
  });
  console.log("saved", name);
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

try {
  await mkdir(outDir, { recursive: true });
  await waitForApp(page);
  await capture(page, "01-bonus-admin");

  await switchRole(page, "hq001");
  await capture(page, "02-hq-evaluator");

  await switchRole(page, "E010");
  await capture(page, "03-evaluator-leader");

  await switchRole(page, "E101");
  await capture(page, "04-employee-self-eval");

  await switchRole(page, "ADMIN001");
  await page.getByRole("button", { name: "考課画面へ" }).click();
  await page.waitForTimeout(2000);
  await capture(page, "05-admin-workspace");

  await switchRole(page, "DIR001");
  await capture(page, "06-director-bonus");
} finally {
  await browser.close();
}
