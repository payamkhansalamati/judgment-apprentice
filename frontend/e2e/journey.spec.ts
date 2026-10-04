import { expect, test } from "@playwright/test";
test("expert correction, confirmation, challenge approval, blocked learner save and correction", async ({
  page,
  request,
}) => {
  test.setTimeout(90000);
  await page.goto("/");
  await page
    .getByRole("button", { name: "Start simulated demo", exact: true })
    .click();
  await page
    .getByRole("checkbox", {
      name: "I consent to capturing this synthetic review and its answers.",
    })
    .check();
  await page
    .getByLabel("Justification", { exact: true })
    .fill("Hold until the report matches the release.");
  await page
    .getByRole("button", { name: "Save review decision", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Start capture", exact: true })
    .click();
  for (let index = 0; index < 3; index++) {
    await expect(
      page.getByRole("button", { name: "Play scripted answer", exact: true }),
    ).toBeEnabled({ timeout: 12000 });
    await page
      .getByRole("button", { name: "Play scripted answer", exact: true })
      .click();
    await expect(
      page.getByText(`${index + 1}/3 conditions explained`, { exact: false }),
    ).toBeVisible();
  }
  await page
    .getByRole("button", { name: "Start debrief", exact: true })
    .click();
  for (let index = 0; index < 3; index++)
    await page
      .getByRole("button", { name: "Use demo answer" })
      .nth(index)
      .click();
  await expect(page.getByText("Unresolved", { exact: true })).toHaveCount(0);
  const correction = "Also require security regression tests before approval.";
  await page.getByLabel("Correction in the expert’s words").fill(correction);
  await page
    .getByRole("button", { name: "Review proposed correction", exact: true })
    .click();
  await expect(
    page.getByText("simulated · ready", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Apply reviewed correction", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Review teach-back", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm this map", exact: true })
    .click();
  await expect(
    page.getByText("Map v1 · approved.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Match release and report versions",
      exact: false,
    })
    .click();
  await page
    .getByRole("button", { name: "Screen moment 1", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("sandbox case snapshot");
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .getByRole("button", { name: "Approve challenge", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Approve challenge", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Begin training", exact: false })
    .click();
  await page.getByLabel("Why?").fill("All tests passed.");
  await page
    .getByRole("button", { name: "Save first answer", exact: true })
    .click();
  await expect(
    page.getByText("Pause: the evidence does not support this answer.", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Tests do not cover: security regression.", {
      exact: false,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Ask for expert evidence", exact: true })
    .click();
  await page.getByLabel("Your decision").selectOption("Hold");
  await page
    .getByLabel("Why?")
    .fill("Missing security regression test coverage.");
  await page
    .getByRole("button", { name: "Save corrected answer", exact: true })
    .click();
  await expect(page.getByText("Decision saved", { exact: true })).toBeVisible();
  await expect(page.getByText("hinted", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Unseen assessment", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Ask for expert evidence", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Your decision").selectOption("Hold");
  await page
    .getByLabel("Why?")
    .fill("The reviewer is the same person as the author.");
  await page
    .getByRole("button", { name: "Save first answer", exact: true })
    .click();
  await expect(page.getByText("Decision saved", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "View results", exact: true }).click();
  await expect(
    page.getByText("What the learner demonstrated", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("independent", { exact: true })).toBeVisible();
  const sessionId = await page.evaluate(() =>
    localStorage.getItem("ja-session"),
  );
  await page.reload();
  await page.getByRole("button", { name: "Results", exact: true }).click();
  await expect(page.getByText("hinted", { exact: true })).toBeVisible();
  await request.delete(`/api/sessions/${sessionId}`);
});

test("live mode gives explicit setup guidance and never presents demo answers", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Start live session", exact: true })
    .click();
  await expect(
    page.getByText("Live mode · capture", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Play scripted answer" }),
  ).toHaveCount(0);
  const sessionId = await page.evaluate(() =>
    localStorage.getItem("ja-session"),
  );
  await request.delete(`/api/sessions/${sessionId}`);
});
