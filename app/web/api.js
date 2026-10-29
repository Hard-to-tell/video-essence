// 前端唯一的数据入口。仅显式 ?mock=1 使用演示数据，断线不会退回演示。
const Api = (() => {
  let mode = null; // "real" | "mock"

  async function http(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw { status: res.status, message: data.message || data.error || `请求失败（${res.status}）` };
    return data;
  }

  async function detect() {
    if (new URLSearchParams(location.search).has("mock")) return (mode = "mock");
    try {
      const s = await http("GET", "/api/status");
      return (mode = "real");
    } catch {
      // 服务不可用时保持真实模式并显示请求失败，避免误把演示结果当真。
      return (mode = "real");
    }
  }

  function call(method, path, body) {
    return mode === "real" ? http(method, path, body) : window.MockBackend.request(method, path, body);
  }

  // 进度推送：真实后端用 SSE（/api/events），断开后改为每 2 秒轮询一次批次列表。
  function subscribe(onEvent) {
    if (mode !== "real") return window.MockBackend.subscribe(onEvent);
    let es, timer;
    const poll = () => {
      clearInterval(timer);
      timer = setInterval(async () => {
        try { onEvent({ type: "refresh", batches: await http("GET", "/api/batches") }); } catch {}
      }, 2000);
    };
    try {
      es = new EventSource("/api/events");
      es.onmessage = (e) => { try { onEvent(JSON.parse(e.data)); } catch {} };
      es.onerror = () => { es.close(); poll(); };
    } catch { poll(); }
    return () => { es && es.close(); clearInterval(timer); };
  }

  return {
    detect,
    get mode() { return mode; },
    status: () => call("GET", "/api/status"),
    batches: () => call("GET", "/api/batches"),
    item: (id) => call("GET", `/api/items/${encodeURIComponent(id)}`),
    library: () => call("GET", "/api/library"),
    createJob: (job) => call("POST", "/api/jobs", job),
    retry: (id) => call("POST", `/api/items/${encodeURIComponent(id)}/retry`),
    cancel: (id) => call("POST", `/api/items/${encodeURIComponent(id)}/cancel`),
    summarizeAnyway: (id) => call("POST", `/api/items/${encodeURIComponent(id)}/summarize`),
    cancelBatch: (id) => call("POST", `/api/batches/${encodeURIComponent(id)}/cancel`),
    settings: () => call("GET", "/api/settings"),
    saveSettings: (s) => call("PUT", "/api/settings", s),
    login: (platform) => call("POST", `/api/accounts/${platform}/login`),
    subscribe,
  };
})();
