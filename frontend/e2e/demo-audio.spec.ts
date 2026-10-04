import { expect, test } from "@playwright/test";
test("demo audio enable, asynchronous voices, test, replay, stop and mute", async ({
  page,
  request,
}) => {
  await page.addInitScript(() => {
    const calls: string[] = [];
    let voices: SpeechSynthesisVoice[] = [];
    let listener: (() => void) | undefined;
    Object.assign(window, { __speechCalls: calls });
    Object.defineProperty(window, "SpeechSynthesisUtterance", {
      value: function (text: string) {
        return {
          text,
          voice: null,
          lang: "",
          onstart: null,
          onend: null,
          onerror: null,
        };
      },
    });
    Object.defineProperty(window, "speechSynthesis", {
      value: {
        speaking: false,
        cancel: () => {},
        resume: () => {},
        getVoices: () => voices,
        addEventListener: (_name: string, callback: () => void) => {
          listener = callback;
        },
        speak: (utterance: SpeechSynthesisUtterance) => {
          calls.push(utterance.text);
          setTimeout(() => {
            utterance.onstart?.(new Event("start") as SpeechSynthesisEvent);
            utterance.onend?.(new Event("end") as SpeechSynthesisEvent);
          }, 500);
        },
      },
    });
    Object.assign(window, {
      __loadVoices: () => {
        voices = [
          {
            lang: "en-US",
            localService: true,
            name: "Test",
            default: true,
            voiceURI: "test",
          },
        ];
        listener?.();
      },
    });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Start simulated demo", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Enable demo audio", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Training", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Return to Expert workspace",
      exact: true,
    })
    .click();

  await page
    .getByRole("checkbox", {
      name: "I consent to capturing this synthetic review and its answers.",
    })
    .check();
  await page
    .getByRole("button", { name: "Enable demo audio", exact: true })
    .click();
  await expect(
    page.getByText("Audio enabled. Browser playback completed.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.evaluate(() => {
    (window as unknown as { __loadVoices: () => void }).__loadVoices();
  });
  await page.getByRole("button", { name: "Test voice", exact: true }).click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          (window as unknown as { __speechCalls: string[] }).__speechCalls
            .length,
      ),
    )
    .toBe(2);
  await expect(
    page.getByText("Audio enabled. Browser playback completed.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Ask now", exact: true }).click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          (window as unknown as { __speechCalls: string[] }).__speechCalls
            .length,
      ),
    )
    .toBe(3);
  await page
    .getByRole("button", { name: "Replay question", exact: true })
    .click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          (window as unknown as { __speechCalls: string[] }).__speechCalls
            .length,
      ),
    )
    .toBe(4);
  await page.getByRole("button", { name: "Stop voice", exact: true }).click();
  await page.getByRole("button", { name: "Mute audio", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Test voice", exact: true }),
  ).toBeDisabled();
  const id = await page.evaluate(() => localStorage.getItem("ja-session"));
  await request.delete(`/api/sessions/${id}`);
});
