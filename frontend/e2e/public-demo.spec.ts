import { expect, test } from "@playwright/test";

test("public production demo hides live/uploads/listing and isolates visitors", async ({
  page,
  request,
  browser,
}) => {
  test.skip(
    process.env.JA_E2E_PUBLIC_DEMO !== "true",
    "Public production mode only.",
  );
  await page.goto("/");
  await expect(page.getByText(/Your demo data may reset/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start live session", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Your sessions", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Start simulated demo", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Share selected screen", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Simulated demo · capture", { exact: true }),
  ).toBeVisible();
  const id = await page.evaluate(() => localStorage.getItem("ja-session"));
  const stranger = await browser.newContext();
  try {
    const response = await stranger.request.get(
      `${new URL(page.url()).origin}/api/sessions/${id}`,
    );
    expect(response.status()).toBe(404);
  } finally {
    await stranger.close();
  }
  expect((await request.get("/api/unknown")).status()).toBe(404);
  expect((await request.get("/api/sessions")).status()).toBe(403);
  expect((await page.request.delete(`/api/sessions/${id}`)).status()).toBe(200);
});
