interface ErrorBody {
  detail?: string | { msg?: string }[];
  violations?: { explanation: string }[];
}

export async function api<T>(
  path: string,
  body?: unknown,
  method?: "DELETE",
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: method ?? (body === undefined ? "GET" : "POST"),
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("The local backend is unavailable. Start it and retry.");
  }
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new Error(
      "The local API did not respond. Check the backend and retry.",
    );
  }
  const result: unknown = await response.json();
  if (!response.ok) {
    const error = result as ErrorBody;
    const detail =
      typeof error.detail === "string"
        ? error.detail
        : error.detail?.map((issue) => issue.msg ?? "Invalid input").join(" ");
    throw new Error(
      detail ??
        error.violations?.map((v) => v.explanation).join(" ") ??
        "The request failed. Retry.",
    );
  }
  return result as T;
}
