import { useCallback, useEffect, useRef, useState } from "react";
import type { Event } from "./contracts";

const FRAME_INTERVAL_MS = 1500;
const MAX_FRAME_DIMENSION = 960;
const STABILITY_THRESHOLD = 5;

/** Fractions of the selected shared surface, applied before a frame leaves the browser. */
export interface ScreenMask {
  x: number;
  y: number;
  width: number;
  height: number;
}
export interface ScreenCaptureOptions {
  sessionId: string;
  enabled: boolean;
  masks?: ScreenMask[];
  onObservation?: (event: Event) => void;
  onError?: (message: string) => void;
}

export function useScreenCapture(options: ScreenCaptureOptions) {
  const latest = useRef(options);
  latest.current = options;
  const stream = useRef<MediaStream | null>(null);
  const video = useRef<HTMLVideoElement | null>(null);
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const sample = useRef<HTMLCanvasElement | null>(null);
  const previousPixels = useRef<Uint8ClampedArray | null>(null);
  const stableFrames = useRef(0);
  const interval = useRef<ReturnType<typeof setInterval> | null>(null);
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const starting = useRef(false);
  const [active, setActive] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [stability, setStability] = useState(false);
  const [lastFrameAt, setLastFrameAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stop = useCallback(() => {
    generation.current += 1;
    starting.current = false;
    request.current?.abort();
    request.current = null;
    if (interval.current !== null) clearInterval(interval.current);
    interval.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    if (video.current) {
      video.current.pause();
      video.current.srcObject = null;
    }
    video.current = null;
    if (canvas.current) canvas.current.width = 0;
    if (sample.current) sample.current.width = 0;
    canvas.current = null;
    sample.current = null;
    previousPixels.current = null;
    stableFrames.current = 0;
    setActive(false);
    setConnecting(false);
    setStability(false);
  }, []);

  const capture = useCallback(
    async (captureGeneration: number) => {
      if (!latest.current.enabled || captureGeneration !== generation.current)
        return;
      const element = video.current;
      const output = canvas.current;
      const thumbnail = sample.current;
      if (!element?.videoWidth || !element.videoHeight || !output || !thumbnail)
        return;
      const context = output.getContext("2d");
      const thumbnailContext = thumbnail.getContext("2d", {
        willReadFrequently: true,
      });
      if (!context || !thumbnailContext) return;
      let frameRequest: AbortController | null = null;

      try {
        const scale = Math.min(
          1,
          MAX_FRAME_DIMENSION /
            Math.max(element.videoWidth, element.videoHeight),
        );
        output.width = Math.max(1, Math.round(element.videoWidth * scale));
        output.height = Math.max(1, Math.round(element.videoHeight * scale));
        context.drawImage(element, 0, 0, output.width, output.height);
        context.fillStyle = "#111827";
        for (const mask of latest.current.masks ?? []) {
          if (
            ![mask.x, mask.y, mask.width, mask.height].every(Number.isFinite) ||
            mask.x < 0 ||
            mask.y < 0 ||
            mask.width <= 0 ||
            mask.height <= 0 ||
            mask.x + mask.width > 1 ||
            mask.y + mask.height > 1
          ) {
            throw new Error(
              "A privacy mask is invalid. Use positions and sizes between 0 and 100%.",
            );
          }
          context.fillRect(
            mask.x * output.width,
            mask.y * output.height,
            mask.width * output.width,
            mask.height * output.height,
          );
        }
        thumbnailContext.drawImage(
          output,
          0,
          0,
          thumbnail.width,
          thumbnail.height,
        );
        const pixels = thumbnailContext.getImageData(
          0,
          0,
          thumbnail.width,
          thumbnail.height,
        ).data;
        const previous = previousPixels.current;
        if (previous) {
          let difference = 0;
          for (let index = 0; index < pixels.length; index += 4) {
            difference += Math.abs(pixels[index] - previous[index]);
            difference += Math.abs(pixels[index + 1] - previous[index + 1]);
            difference += Math.abs(pixels[index + 2] - previous[index + 2]);
          }
          const average = difference / ((pixels.length / 4) * 3);
          stableFrames.current =
            average < STABILITY_THRESHOLD ? stableFrames.current + 1 : 0;
          setStability(stableFrames.current >= 2);
        }
        previousPixels.current = new Uint8ClampedArray(pixels);
        // Skip a frame while vision is busy. There is no frame queue.
        if (request.current) return;
        const controller = new AbortController();
        frameRequest = controller;
        request.current = controller;
        const response = await fetch(
          `/api/sessions/${encodeURIComponent(latest.current.sessionId)}/frames`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              image: output.toDataURL("image/jpeg", 0.72),
            }),
            signal: controller.signal,
          },
        );
        if (captureGeneration !== generation.current || !latest.current.enabled)
          return;
        if (response.status === 429) return;
        if (!response.ok) {
          const body = (await response.json()) as { detail?: string };
          throw new Error(
            body.detail ??
              "Screen observation failed. Check your connection and restart sharing.",
          );
        }
        const event = (await response.json()) as Event;
        if (captureGeneration !== generation.current || !latest.current.enabled)
          return;
        setLastFrameAt(Date.now());
        latest.current.onObservation?.(event);
      } catch (failure) {
        if (captureGeneration !== generation.current) return;
        const message =
          failure instanceof Error
            ? failure.message
            : "Screen sharing failed. Restart sharing.";
        setError(message);
        latest.current.onError?.(message);
        stop();
      } finally {
        if (frameRequest && request.current === frameRequest)
          request.current = null;
      }
    },
    [stop],
  );

  /** Call only from a user action; enabling consent never starts capture automatically. */
  const start = useCallback(async () => {
    if (!latest.current.enabled || stream.current || starting.current) return;
    if (!navigator.mediaDevices?.getDisplayMedia) {
      const message =
        "Screen sharing is unavailable. Use a supported browser on localhost.";
      setError(message);
      latest.current.onError?.(message);
      return;
    }
    starting.current = true;
    setConnecting(true);
    setError(null);
    const captureGeneration = ++generation.current;
    try {
      const selected = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false,
      });
      if (captureGeneration !== generation.current || !latest.current.enabled) {
        selected.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = selected;
      const element = document.createElement("video");
      element.muted = true;
      element.playsInline = true;
      element.srcObject = selected;
      video.current = element;
      await element.play();
      if (captureGeneration !== generation.current || !latest.current.enabled)
        return;
      canvas.current = document.createElement("canvas");
      sample.current = document.createElement("canvas");
      sample.current.width = 32;
      sample.current.height = 18;
      selected
        .getVideoTracks()
        .forEach((track) =>
          track.addEventListener("ended", stop, { once: true }),
        );
      setActive(true);
      interval.current = setInterval(() => {
        void capture(captureGeneration);
      }, FRAME_INTERVAL_MS);
      void capture(captureGeneration);
    } catch (failure) {
      if (captureGeneration !== generation.current) return;
      const message =
        failure instanceof DOMException && failure.name === "NotAllowedError"
          ? "Screen sharing was declined. You can continue with the sandbox or try again."
          : "Could not start screen sharing. Check browser permissions and try again.";
      setError(message);
      latest.current.onError?.(message);
      stop();
    } finally {
      if (captureGeneration === generation.current) {
        starting.current = false;
        setConnecting(false);
      }
    }
  }, [capture, stop]);

  useEffect(() => {
    if (!options.enabled) stop();
  }, [options.enabled, stop]);
  useEffect(() => () => stop(), [options.sessionId, stop]);

  return { start, stop, active, connecting, lastFrameAt, stability, error };
}
