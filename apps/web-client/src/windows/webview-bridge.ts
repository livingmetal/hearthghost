export interface WindowsWebViewHost {
  postMessage(message: unknown): void;
  addEventListener(type: "message", listener: (event: { readonly data: unknown }) => void): void;
  removeEventListener(type: "message", listener: (event: { readonly data: unknown }) => void): void;
}

type WindowsChrome = {
  readonly webview?: WindowsWebViewHost;
};

type WindowWithWebView = Window & {
  readonly chrome?: WindowsChrome;
};

interface BridgeSuccess {
  readonly id: string;
  readonly ok: true;
  readonly result: unknown;
}

interface BridgeFailure {
  readonly id: string;
  readonly ok: false;
  readonly error: string;
}

type BridgeResponse = BridgeSuccess | BridgeFailure;

const MAX_PENDING = 16;
const REQUEST_TIMEOUT_MILLIS = 25_000;
const METHOD_PATTERN = /^[a-z][a-z0-9.]{0,63}$/;

export function windowsWebViewHost(): WindowsWebViewHost | null {
  const candidate = (window as WindowWithWebView).chrome?.webview;
  return candidate ?? null;
}

export function isWindowsWebViewHost(): boolean {
  return windowsWebViewHost() !== null;
}

export class WindowsWebViewBridge {
  private readonly pending = new Map<
    string,
    {
      readonly resolve: (value: unknown) => void;
      readonly reject: (error: Error) => void;
      readonly timer: number;
    }
  >();

  private readonly listener = (event: { readonly data: unknown }): void => {
    let response: BridgeResponse;
    try {
      response = parseBridgeResponse(event.data);
    } catch {
      return;
    }
    const request = this.pending.get(response.id);
    if (request === undefined) {
      return;
    }
    window.clearTimeout(request.timer);
    this.pending.delete(response.id);
    if (response.ok) {
      request.resolve(response.result);
    } else {
      request.reject(new Error(response.error));
    }
  };

  constructor(private readonly host: WindowsWebViewHost) {
    host.addEventListener("message", this.listener);
  }

  request(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    if (!METHOD_PATTERN.test(method)) {
      return Promise.reject(new Error("Windows bridge method is invalid"));
    }
    if (this.pending.size >= MAX_PENDING) {
      return Promise.reject(new Error("Windows bridge request limit exceeded"));
    }
    const id = crypto.randomUUID();
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => {
        this.pending.delete(id);
        reject(new Error("Windows bridge request timed out"));
      }, REQUEST_TIMEOUT_MILLIS);
      this.pending.set(id, { resolve, reject, timer });
      this.host.postMessage(Object.freeze({ id, method, params }));
    });
  }

  dispose(): void {
    this.host.removeEventListener("message", this.listener);
    for (const request of this.pending.values()) {
      window.clearTimeout(request.timer);
      request.reject(new Error("Windows bridge disposed"));
    }
    this.pending.clear();
  }
}

function parseBridgeResponse(value: unknown): BridgeResponse {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Windows bridge response must be an object");
  }
  const record = value as Record<string, unknown>;
  if (typeof record.id !== "string" || record.id.length > 80 || typeof record.ok !== "boolean") {
    throw new Error("Windows bridge response identity is invalid");
  }
  if (record.ok) {
    if (Object.keys(record).some((key) => !["id", "ok", "result"].includes(key))) {
      throw new Error("Windows bridge success response contains unknown fields");
    }
    return { id: record.id, ok: true, result: record.result };
  }
  if (
    Object.keys(record).some((key) => !["id", "ok", "error"].includes(key))
    || typeof record.error !== "string"
    || record.error.length === 0
    || record.error.length > 160
  ) {
    throw new Error("Windows bridge failure response is invalid");
  }
  return { id: record.id, ok: false, error: record.error };
}
