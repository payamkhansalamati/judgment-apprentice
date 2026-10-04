import { expect, test, type Page } from "@playwright/test";

interface PrivacyState {
  uploads: number;
  frameAborts: number;
  inFlight: number;
  maxInFlight: number;
  displayCalls: number;
  micCalls: number;
  trackStops: number;
  providerSockets: number;
  image: string | null;
}

declare global {
  interface Window {
    __privacy: PrivacyState;
    __resolveScreen?: () => void;
    __resolveMic?: () => void;
  }
}

async function instrumentPrivacy(
  page: Page,
  pendingScreen = false,
  pendingMicrophone = false,
) {
  await page.addInitScript(
    ({ pendingScreen, pendingMicrophone }) => {
      const target = window;
      const state: PrivacyState = (target.__privacy = {
        uploads: 0,
        frameAborts: 0,
        inFlight: 0,
        maxInFlight: 0,
        displayCalls: 0,
        micCalls: 0,
        trackStops: 0,
        providerSockets: 0,
        image: null,
      });
      const makeScreen = () => {
        const canvas = document.createElement("canvas");
        canvas.width = 1600;
        canvas.height = 900;
        const context = canvas.getContext("2d");
        if (!context) throw new Error("Canvas is required for capture tests.");
        context.fillStyle = "#ffffff";
        context.fillRect(0, 0, 1600, 900);
        context.fillStyle = "#ff0000";
        context.fillRect(0, 0, 1600, 100);
        const stream = canvas.captureStream(5);
        stream.getTracks().forEach((track) => {
          const originalStop = track.stop.bind(track);
          track.stop = () => {
            state.trackStops += 1;
            originalStop();
          };
        });
        return stream;
      };
      Object.defineProperty(navigator.mediaDevices, "getDisplayMedia", {
        configurable: true,
        value: () => {
          state.displayCalls += 1;
          if (!pendingScreen) return Promise.resolve(makeScreen());
          return new Promise<MediaStream>((resolve) => {
            target.__resolveScreen = () => resolve(makeScreen());
          });
        },
      });
      Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
        configurable: true,
        value: () => {
          state.micCalls += 1;
          if (!pendingMicrophone)
            return Promise.reject(
              new Error("Simulated mode must not request microphone access."),
            );
          return new Promise<MediaStream>((resolve) => {
            target.__resolveMic = () => resolve(makeScreen());
          });
        },
      });
      const OriginalWebSocket = window.WebSocket;
      window.WebSocket = class extends OriginalWebSocket {
        constructor(url: string | URL, protocols?: string | string[]) {
          if (
            new URL(String(url), location.href).hostname !== location.hostname
          )
            state.providerSockets += 1;
          super(url, protocols);
        }
      };
      const originalFetch = window.fetch.bind(window);
      window.fetch = (input, init) => {
        const url = input instanceof Request ? input.url : String(input);
        if (!url.endsWith("/frames")) return originalFetch(input, init);
        state.uploads += 1;
        state.inFlight += 1;
        state.maxInFlight = Math.max(state.maxInFlight, state.inFlight);
        state.image = (
          JSON.parse(String(init?.body)) as { image: string }
        ).image;
        return new Promise<Response>((resolve, reject) => {
          let settled = false;
          const finish = () => {
            if (!settled) {
              settled = true;
              state.inFlight -= 1;
            }
          };
          const timer = setTimeout(() => {
            if (settled) return;
            finish();
            resolve(
              new Response(
                JSON.stringify({
                  event_id: "privacy-frame",
                  session_id: "privacy",
                  event_type: "screen_observation",
                  timestamp: new Date().toISOString(),
                  source: "simulated",
                  payload: { summary: "Mocked frame" },
                }),
                {
                  status: 200,
                  headers: { "Content-Type": "application/json" },
                },
              ),
            );
          }, 10000);
          init?.signal?.addEventListener(
            "abort",
            () => {
              if (settled) return;
              finish();
              clearTimeout(timer);
              state.frameAborts += 1;
              reject(new DOMException("Capture stopped", "AbortError"));
            },
            { once: true },
          );
        });
      };
    },
    { pendingScreen, pendingMicrophone },
  );
}

async function startConsentedSession(page: Page, live = false) {
  await page.goto("/");
  await page
    .getByRole("button", {
      name: live ? "Start live session" : "Start simulated demo",
      exact: true,
    })
    .click();
  await page
    .getByRole("checkbox", {
      name: "I consent to capturing this synthetic review and its answers.",
    })
    .check();
  await expect(
    page.getByRole("button", { name: "Share selected screen" }),
  ).toBeEnabled();
}

test("capture masks resized frames, applies backpressure, and off-record stops transmission", async ({
  page,
}) => {
  await instrumentPrivacy(page);
  await startConsentedSession(page);
  await expect
    .poll(() => page.evaluate(() => window.__privacy.displayCalls))
    .toBe(0);
  await page.getByRole("button", { name: "Share selected screen" }).click();
  await expect
    .poll(() => page.evaluate(() => window.__privacy.uploads))
    .toBe(1);
  const pixels = await page.evaluate(async () => {
    const image = new Image();
    image.src = window.__privacy.image ?? "";
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas unavailable.");
    context.drawImage(image, 0, 0);
    return {
      width: image.width,
      height: image.height,
      top: Array.from(context.getImageData(20, 20, 1, 1).data),
      bottom: Array.from(
        context.getImageData(20, image.height - 20, 1, 1).data,
      ),
    };
  });
  expect(pixels.width).toBe(960);
  expect(pixels.height).toBe(540);
  expect(pixels.top[0]).toBeLessThan(30);
  expect(pixels.top[1]).toBeLessThan(40);
  expect(pixels.bottom[0]).toBeGreaterThan(240);
  await page.waitForTimeout(3200);
  expect(await page.evaluate(() => window.__privacy.uploads)).toBe(1);
  await page.getByRole("button", { name: "Go off record" }).click();
  await expect(
    page.getByRole("button", { name: "Resume recording" }),
  ).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => window.__privacy.trackStops))
    .toBe(1);
  await expect
    .poll(() => page.evaluate(() => window.__privacy.frameAborts))
    .toBe(1);
  await page.waitForTimeout(1700);
  const state = await page.evaluate(() => window.__privacy);
  expect(state.uploads).toBe(1);
  expect(state.inFlight).toBe(0);
  expect(state.maxInFlight).toBe(1);
  expect(state.micCalls).toBe(0);
  expect(state.providerSockets).toBe(0);
});

test("off-record closes a shared stream granted after the screen picker was opened", async ({
  page,
}) => {
  await instrumentPrivacy(page, true);
  await startConsentedSession(page);
  await page.getByRole("button", { name: "Share selected screen" }).click();
  await expect
    .poll(() => page.evaluate(() => window.__privacy.displayCalls))
    .toBe(1);
  await page.getByRole("button", { name: "Go off record" }).click();
  await expect(
    page.getByRole("button", { name: "Resume recording" }),
  ).toBeVisible();
  await page.evaluate(() => window.__resolveScreen?.());
  await expect
    .poll(() => page.evaluate(() => window.__privacy.trackStops))
    .toBe(1);
  const state = await page.evaluate(() => window.__privacy);
  expect(state.uploads).toBe(0);
  expect(state.micCalls).toBe(0);
});

test("off-record releases a late microphone permission without connecting to the voice provider", async ({
  page,
}) => {
  await instrumentPrivacy(page, false, true);
  await page.route("**/api/sessions/*/voice/interviewer", (route) =>
    route.fulfill({
      json: { signed_url: "wss://voice.example.invalid/session" },
    }),
  );
  await startConsentedSession(page, true);
  await page
    .getByRole("checkbox", {
      name: "I allow microphone access for this live conversation.",
    })
    .check();
  await page
    .getByRole("button", { name: "Connect voice", exact: true })
    .click();
  await expect
    .poll(() => page.evaluate(() => window.__privacy.micCalls))
    .toBe(1);
  await page.getByRole("button", { name: "Go off record" }).click();
  await expect(
    page.getByRole("button", { name: "Resume recording" }),
  ).toBeVisible();
  await page.evaluate(() => window.__resolveMic?.());
  await expect
    .poll(() => page.evaluate(() => window.__privacy.trackStops))
    .toBe(1);
  await expect(
    page.getByText("Off record · audio disconnected", { exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => window.__privacy.providerSockets)).toBe(0);
});
