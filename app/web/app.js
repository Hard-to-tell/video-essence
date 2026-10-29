// 界面逻辑：四个页面（开始 / 进度 / 总结库 / 设置）+ 右侧详情抽屉。
// 只通过 Api 取数据，不直接碰后端细节。
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const state = {
  view: "home",
  status: null,
  batches: [],
  library: [],
  settings: null,
  composer: { source: null, limit: 5, autoSkip: true, links: "", files: [] },
  lib: { q: "", platform: "all", verdict: "all" },
  drawer: { id: null, tab: "summary", data: null, q: "" },
};

// ---------- 文案与小工具 ----------
const STATUS = {
  queued: ["排队中", "queued"], running: ["进行中", "running"], done: ["已完成", "done"],
  skipped: ["已跳过", "skipped"], failed: ["失败", "failed"], canceled: ["已取消", "canceled"],
};
const VERDICT = { essence: "有干货", some: "少量干货", none: "没有精华" };
const STAGES = [
  ["meta", "读取视频信息"],
  ["content", "获取正文（字幕或听写）"],
  ["judge", "判断值不值得总结"],
  ["summarize", "提炼精华"],
];
const PLATFORM = { bilibili: "B站", douyin: "抖音", local: "本地" };
const ICON = {
  bili: '<svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="13" rx="3"/><path d="M8 3l2 3M16 3l-2 3M9 12v1M15 12v1"/></svg>',
  douyin: '<svg viewBox="0 0 24 24"><path d="M14 3v11.5a3.5 3.5 0 1 1-3.5-3.5"/><path d="M14 3c.5 2.5 2.3 4.2 5 4.5"/></svg>',
  link: '<svg viewBox="0 0 24 24"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>',
  file: '<svg viewBox="0 0 24 24"><path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5M10 12l4 2.5-4 2.5z"/></svg>',
  spark: '<svg viewBox="0 0 24 24"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  skip: '<svg viewBox="0 0 24 24"><path d="M5 5l8 7-8 7zM17 5v14"/></svg>',
  retry: '<svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 1 0 2.4-5.7L4 8.5"/><path d="M4 4v4.5h4.5"/></svg>',
  copy: '<svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg>',
  open: '<svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>',
  sun: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6L19 19M5 19l1.4-1.4M17.6 6.4L19 5"/></svg>',
  moon: '<svg viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>',
};

function fmtDur(sec) {
  sec = Math.max(0, Math.round(sec || 0));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}
function fmtEta(sec) {
  if (sec == null) return "";
  if (sec < 60) return `约 ${Math.max(1, Math.round(sec))} 秒`;
  return `约 ${Math.round(sec / 60)} 分钟`;
}
function fmtAgo(iso) {
  const d = (Date.now() - new Date(iso)) / 1000;
  if (d < 60) return "刚刚";
  if (d < 3600) return `${Math.floor(d / 60)} 分钟前`;
  if (d < 86400) return `${Math.floor(d / 3600)} 小时前`;
  return `${Math.floor(d / 86400)} 天前`;
}
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 2400);
}
function pill(status) {
  const [label, cls] = STATUS[status] || [status, "queued"];
  const icon = status === "running" ? '<span class="spinner" style="width:11px;height:11px;border-width:2px"></span>'
    : status === "done" ? ICON.check : status === "failed" ? ICON.x : status === "skipped" ? ICON.skip : "";
  return `<span class="pill ${cls}">${icon}${label}</span>`;
}
function verdictPill(v) {
  return v ? `<span class="pill verdict ${v}">${VERDICT[v]}</span>` : "";
}
function thumb(it) {
  const inner = it.cover ? `<img src="${esc(it.cover)}" alt="">` : esc(PLATFORM[it.platform] || "");
  const bg = it.cover ? "" : `style="background:linear-gradient(135deg, ${it.color || "#7c6cf0"}, ${it.color || "#7c6cf0"}99)"`;
  return `<div class="thumb" ${bg}>${inner}<span>${fmtDur(it.duration)}</span></div>`;
}
function timeLink(it, t) {
  let url = it.url || "";
  if (it.platform === "bilibili" && url) url += (url.includes("?") ? "&" : "?") + `t=${Math.floor(t)}`;
  return url ? `<a class="tstamp" href="${esc(url)}" target="_blank" rel="noopener" title="在原视频中打开">${fmtDur(t)}</a>`
    : `<span class="tstamp">${fmtDur(t)}</span>`;
}
function stageIndex(stage) { return STAGES.findIndex((s) => s[0] === stage); }

// ---------- 侧边栏 ----------
function renderSys() {
  const s = state.status;
  const theme = document.documentElement.dataset.theme || "auto";
  const themeLabel = { auto: "跟随系统", light: "浅色", dark: "深色" }[theme];
  if (!s) { $("#sys").innerHTML = ""; return; }
  const gpu = s.gpu;
  const pct = gpu ? Math.round((gpu.mem_used_mb / gpu.mem_total_mb) * 100) : 0;
  const acct = (k, label) => {
    const a = (s.accounts || {})[k] || {};
    return `<div class="sys-row"><i class="dot ${a.logged_in ? "ok" : "warn"}"></i>${label}<b>${a.logged_in ? "已登录" : "未登录"}</b></div>`;
  };
  $("#sys").innerHTML = `
    <div class="sys-row"><i class="dot ${gpu ? "ok" : "warn"}"></i>${gpu ? esc(gpu.name) : "未检测到显卡"}<b>${gpu ? `${(gpu.mem_used_mb / 1024).toFixed(1)}/${(gpu.mem_total_mb / 1024).toFixed(0)} GB` : "CPU"}</b></div>
    ${gpu ? `<div class="meter"><i style="width:${pct}%"></i></div>` : ""}
    <div class="sys-row"><i class="dot ok"></i>听写模型<b>${esc(s.model || "")}</b></div>
    ${acct("bilibili", "B站")}
    ${acct("douyin", "抖音")}
    <button class="theme-btn" id="theme-btn">${theme === "dark" ? ICON.moon : ICON.sun}外观：${themeLabel}</button>`;
  $("#theme-btn").onclick = cycleTheme;
}
function cycleTheme() {
  const order = ["auto", "light", "dark"];
  const cur = document.documentElement.dataset.theme || "auto";
  const next = order[(order.indexOf(cur) + 1) % 3];
  if (next === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = next;
  try { localStorage.setItem("theme", next); } catch {}
  renderSys();
}
function renderNavBadge() {
  const n = state.batches.reduce((a, b) => a + b.counts.running + b.counts.queued, 0);
  const el = $("#nav-running");
  el.hidden = !n;
  el.textContent = n;
}

// ---------- 开始页 ----------
const SOURCES = [
  { key: "bilibili", icon: "bili", title: "B站稍后再看", desc: "拉取你 B 站稍后再看列表里最近的视频", account: "bilibili" },
  { key: "douyin", icon: "douyin", title: "抖音稍后再看", desc: "拉取你抖音稍后再看里最近的视频", account: "douyin" },
  { key: "links", icon: "link", title: "粘贴链接", desc: "一次贴多条 B 站或抖音链接，一行一条" },
  { key: "files", icon: "file", title: "本地文件", desc: "已经下载好的音频或视频，直接听写提炼" },
];
const PROMPTS = ["帮我总结一下抖音最近稍后再看的视频", "B站稍后再看里最近 10 条", "把今天加进稍后再看的都过一遍"];

function viewHome() {
  return `
    <section class="card hero">
      <h1>今天想消化点什么？</h1>
      <p>一句话交给我，我去拿视频、听写、提炼，没价值的自动跳过。</p>
      <form class="ask" id="ask">
        ${ICON.spark}
        <input id="ask-input" autocomplete="off" placeholder="例如：帮我总结一下抖音最近稍后再看的视频，或直接粘贴链接">
        <button class="btn primary" type="submit">开始</button>
      </form>
      <div class="chips">${PROMPTS.map((p) => `<button class="chip" data-prompt="${esc(p)}">${esc(p)}</button>`).join("")}</div>
    </section>

    <div class="sources">
      ${SOURCES.map((s) => {
        const a = s.account && state.status?.accounts?.[s.account];
        const st = s.account ? `<span class="state"><i class="dot ${a?.logged_in ? "ok" : "warn"}"></i>${a?.logged_in ? "已登录" : "需登录"}</span>` : "";
        return `<button class="card source ${state.composer.source === s.key ? "on" : ""}" data-source="${s.key}">
          ${st}<div class="ico ${s.icon}">${ICON[s.icon]}</div><b>${s.title}</b><small>${s.desc}</small></button>`;
      }).join("")}
    </div>
    <div id="composer"></div>
    <div id="home-live"></div>`;
}

function renderComposer() {
  const c = state.composer;
  if(c.source === "douyin" && ![1,3,5,9].includes(c.limit)) c.limit=5;
  const box = $("#composer");
  if (!box) return;
  if (!c.source) { box.innerHTML = ""; return; }
  const src = SOURCES.find((s) => s.key === c.source);
  const acct = src.account && state.status?.accounts?.[src.account];
  let body = "";
  if (c.source === "bilibili" || c.source === "douyin") {
    body = `
      ${acct && !acct.logged_in ? `<div class="note">还没登录${PLATFORM[src.account]}，读取稍后再看需要先登录。<button class="link" data-login="${src.account}">现在登录</button></div>` : ""}
      <div class="composer-row">
        <div class="inline">处理最近
          <div class="seg" id="limit-seg">${(c.source === "douyin" ? [1, 3, 5, 9] : [5, 10, 20, 0]).map((n) => `<button data-limit="${n}" class="${c.limit === n ? "on" : ""}">${n ? n + " 条" : "全部"}</button>`).join("")}</div>
        </div>
        <label class="inline"><span class="switch"><input type="checkbox" id="auto-skip" ${c.autoSkip ? "checked" : ""}><span></span></span>自动跳过没价值的视频</label>
      </div>`;
  } else if (c.source === "links") {
    body = `
      <textarea class="input" id="links" placeholder="一行一条，支持 B 站和抖音的分享链接或 BV 号">${esc(c.links)}</textarea>
      <label class="inline"><span class="switch"><input type="checkbox" id="auto-skip" ${c.autoSkip ? "checked" : ""}><span></span></span>自动跳过没价值的视频</label>`;
  } else {
    body = `
      <div class="drop" id="drop">
        <b>把音频或视频文件拖到这里</b><br>
        <span style="font-size:13px">或者在下面填完整路径，一行一个</span>
        ${c.files.length ? `<div class="file-list">${c.files.map((f) => `<div>${esc(f)}</div>`).join("")}</div>` : ""}
      </div>
      <textarea class="input" id="paths" placeholder="D:\\Downloads\\某个视频.mp4">${esc(c.files.join("\n"))}</textarea>`;
  }
  box.innerHTML = `
    <section class="card composer">
      <div class="composer-head"><div class="ico ${src.icon}" style="width:30px;height:30px;border-radius:9px;display:grid;place-items:center">${ICON[src.icon]}</div><b>${src.title}</b>
        <button class="btn ghost sm" style="margin-left:auto" id="composer-close">收起</button></div>
      ${body}
      <div class="composer-foot"><button class="btn primary" id="composer-go">开始处理</button></div>
    </section>`;
  bindComposer();
}

function bindComposer() {
  const c = state.composer;
  $("#composer-close").onclick = () => { c.source = null; renderView(); };
  $("#limit-seg")?.addEventListener("click", (e) => {
    const b = e.target.closest("[data-limit]");
    if (!b) return;
    c.limit = Number(b.dataset.limit);
    renderComposer();
  });
  $("#auto-skip")?.addEventListener("change", (e) => (c.autoSkip = e.target.checked));
  $("#links")?.addEventListener("input", (e) => (c.links = e.target.value));
  $("#paths")?.addEventListener("input", (e) => (c.files = e.target.value.split("\n").map((s) => s.trim()).filter(Boolean)));
  const drop = $("#drop");
  if (drop) {
    drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
    drop.ondragleave = () => drop.classList.remove("over");
    drop.ondrop = (e) => {
      e.preventDefault();
      drop.classList.remove("over");
      // 浏览器拿不到完整路径，只有文件名；真实后端可改为上传（见交接文档）
      const names = [...e.dataTransfer.files].map((f) => f.path || f.name);
      c.files = [...new Set([...c.files, ...names])];
      renderComposer();
    };
  }
  document.querySelectorAll("[data-login]").forEach((b) => (b.onclick = () => login(b.dataset.login)));
  $("#composer-go").onclick = submitComposer;
}

async function submitComposer() {
  const c = state.composer;
  let job;
  if (c.source === "bilibili" || c.source === "douyin") job = { kind: "watch_later", platform: c.source, limit: c.limit, auto_skip: c.autoSkip };
  else if (c.source === "links") {
    const links = c.links.split(/\s+/).map((s) => s.trim()).filter(Boolean);
    if (!links.length) return toast("先粘贴至少一条链接");
    job = { kind: "links", links, auto_skip: c.autoSkip, platform: links[0].includes("douyin") ? "douyin" : "bilibili" };
  } else {
    if (!c.files.length) return toast("先选择或填写文件路径");
    job = { kind: "files", files: c.files, auto_skip: false, platform: "local" };
  }
  await startJob(job);
  Object.assign(c, { source: null, links: "", files: [] });
}

async function startJob(job) {
  try {
    await Api.createJob(job);
    toast("已加入队列");
    await refreshBatches();
    go("queue");
  } catch (e) {
    toast(e.message || "提交失败");
  }
}

function parseAsk(text) {
  const links = text.match(/https?:\/\/\S+|BV[0-9A-Za-z]{10}/g);
  if (links) return { kind: "links", links, auto_skip: true, platform: /douyin/.test(text) ? "douyin" : "bilibili" };
  const n = Number((text.match(/(\d+)\s*条/) || [])[1]) || (/抖音|douyin/i.test(text) ? 5 : 10);
  return { kind: "prompt", prompt: text, limit: n, auto_skip: true, platform: /抖音|douyin/i.test(text) ? "douyin" : "bilibili" };
}

function bindHome() {
  $("#ask").onsubmit = (e) => {
    e.preventDefault();
    const v = $("#ask-input").value.trim();
    if (!v) return $("#ask-input").focus();
    startJob(parseAsk(v));
  };
  document.querySelectorAll("[data-prompt]").forEach((b) => (b.onclick = () => { $("#ask-input").value = b.dataset.prompt; $("#ask-input").focus(); }));
  document.querySelectorAll("[data-source]").forEach((b) => (b.onclick = () => {
    state.composer.source = state.composer.source === b.dataset.source ? null : b.dataset.source;
    renderComposer();
    $("#composer")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }));
  renderComposer();
  renderHomeLive();
}

function renderHomeLive() {
  const box = $("#home-live");
  if (!box) return;
  const active = state.batches.filter((b) => b.counts.running || b.counts.queued);
  const recent = state.batches.flatMap((b) => b.items).filter((i) => i.status === "done").slice(0, 3);
  box.innerHTML = `
    <div class="overview">
      <div>
        <div class="section-title"><h2>正在处理</h2>${active.length ? `<button class="link" data-go="queue">查看全部</button>` : ""}</div>
        ${active.length ? active.map((b) => batchCard(b, 3)).join("") : `<div class="card empty"><b>现在没有任务</b>选一个来源，或者在上面说一句话就能开始</div>`}
      </div>
      <div>
        <div class="section-title"><h2>最新精华</h2>${recent.length ? `<button class="link" data-go="library">总结库</button>` : ""}</div>
        <div style="display:flex;flex-direction:column;gap:12px">
          ${recent.length ? recent.map(sumCard).join("") : `<div class="card empty"><b>还没有总结</b>完成的视频会出现在这里</div>`}
        </div>
      </div>
    </div>`;
  bindLive(box);
}

// ---------- 进度页 ----------
function batchCard(b, limit) {
  const t = b.total || 1, c = b.counts;
  const runningProg = b.items.filter((i) => i.status === "running").reduce((a, i) => a + i.progress, 0);
  const pct = Math.round(((c.done + c.skipped + c.failed + c.canceled + runningProg) / t) * 100);
  const w = (n) => (n / t) * 100;
  const icon = b.platform === "douyin" ? "douyin" : b.platform === "local" ? "file" : b.kind === "links" ? "link" : "bili";
  const items = limit ? sortItems(b.items).slice(0, limit) : b.items;
  const live = c.running || c.queued;
  return `
    <section class="card batch">
      <div class="batch-head">
        <div class="ico ${icon}">${ICON[icon]}</div>
        <div>
          <div class="batch-title">${esc(b.title)}</div>
          <div class="batch-meta">
            <span>${t} 条 · ${fmtAgo(b.created_at)}</span>
            ${c.done ? `<span class="c-ok">完成 ${c.done}</span>` : ""}
            ${c.skipped ? `<span class="c-skip">跳过 ${c.skipped}</span>` : ""}
            ${c.failed ? `<span class="c-bad">失败 ${c.failed}</span>` : ""}
            ${live ? `<span>剩余 ${c.running + c.queued}</span>` : ""}
          </div>
        </div>
        <div class="batch-progress">
          <div class="pct">${live ? pct + "%" : "已结束"}</div>
          <div class="bar"><i class="b-ok" style="width:${w(c.done)}%"></i><i class="b-skip" style="width:${w(c.skipped + c.canceled)}%"></i><i class="b-bad" style="width:${w(c.failed)}%"></i><i class="b-run" style="width:${w(runningProg)}%"></i></div>
        </div>
        ${live && !limit ? `<button class="btn sm ghost" data-cancel-batch="${b.id}">全部取消</button>` : ""}
      </div>
      ${items.map(itemRow).join("")}
      ${limit && b.items.length > limit ? `<div class="item" data-go="queue" style="grid-template-columns:1fr;color:var(--text-3);font-size:13px">还有 ${b.items.length - limit} 条…</div>` : ""}
    </section>`;
}
function sortItems(items) {
  const order = { running: 0, queued: 1, failed: 2, done: 3, skipped: 4, canceled: 5 };
  return [...items].sort((a, b) => order[a.status] - order[b.status]);
}
function itemRow(it) {
  let sub = `<span class="plat ${it.platform}">${PLATFORM[it.platform] || ""}</span>${it.uploader ? `<span>${esc(it.uploader)}</span>` : ""}<span>${fmtDur(it.duration)}</span>`;
  let extra = "";
  if (it.status === "running") {
    const si = stageIndex(it.stage);
    const steps = STAGES.map((s, i) => `<i class="${i < si ? "done" : i === si ? "now" : ""}"></i>`).join("");
    extra = `<div class="run-line"><div class="steps">${steps}</div><div class="bar"><i class="b-run" style="width:${Math.round(it.progress * 100)}%"></i></div>
      <small>${esc(it.message || STAGES[si]?.[1] || "")}${it.eta_sec != null ? " · " + fmtEta(it.eta_sec) : ""}</small></div>`;
  } else if (it.status === "skipped") sub += `<span>· ${esc(it.skip_reason || "")}</span>`;
  else if (it.status === "failed") sub += `<span style="color:var(--bad)">· ${esc(it.error || "")}</span>`;
  else if (it.status === "done" && it.summary) sub += `<span>· ${esc(it.summary.one_line).slice(0, 48)}…</span>`;
  const side = it.status === "done" ? verdictPill(it.summary?.verdict) || pill(it.status)
    : it.status === "failed" ? `<button class="btn sm" data-retry="${it.id}">${ICON.retry}重试</button>${pill(it.status)}`
    : pill(it.status);
  return `<div class="item" data-open="${it.id}">${thumb(it)}<div class="item-main"><div class="item-title">${esc(it.title)}</div><div class="item-sub">${sub}</div>${extra}</div><div class="item-side">${side}</div></div>`;
}

const queueFilter = { value: "all" };
function viewQueue() {
  return `
    <div class="page-head">
      <div><h1>进度</h1><p>每条视频走四步：读取信息、拿到正文、判断价值、提炼精华。长视频会分段听写。</p></div>
      <div class="seg" id="queue-filter">
        ${[["all", "全部"], ["live", "进行中"], ["ended", "已结束"]].map(([k, l]) => `<button data-qf="${k}" class="${queueFilter.value === k ? "on" : ""}">${l}</button>`).join("")}
      </div>
    </div>
    <div id="queue-list"></div>`;
}
function renderQueueList() {
  const box = $("#queue-list");
  if (!box) return;
  let list = state.batches;
  if (queueFilter.value === "live") list = list.filter((b) => b.counts.running || b.counts.queued);
  if (queueFilter.value === "ended") list = list.filter((b) => !(b.counts.running || b.counts.queued));
  box.innerHTML = list.length ? list.map((b) => batchCard(b)).join("") : `<div class="card empty"><b>这里还是空的</b><button class="link" data-go="home">去开始一个任务</button></div>`;
  bindLive(box);
}
function bindQueue() {
  $("#queue-filter").onclick = (e) => {
    const b = e.target.closest("[data-qf]");
    if (!b) return;
    queueFilter.value = b.dataset.qf;
    document.querySelectorAll("[data-qf]").forEach((x) => x.classList.toggle("on", x === b));
    renderQueueList();
  };
  renderQueueList();
}

// 列表里的点击（打开详情、重试、跳转）统一委托
function bindLive(root) {
  root.onclick = async (e) => {
    const retry = e.target.closest("[data-retry]");
    if (retry) { e.stopPropagation(); await Api.retry(retry.dataset.retry); toast("已重新排队"); return refreshBatches(); }
    const cb = e.target.closest("[data-cancel-batch]");
    if (cb) { e.stopPropagation(); await Api.cancelBatch(cb.dataset.cancelBatch); toast("已取消剩余的视频"); return refreshBatches(); }
    const g = e.target.closest("[data-go]");
    if (g) return go(g.dataset.go);
    const o = e.target.closest("[data-open]");
    if (o) openDrawer(o.dataset.open);
  };
}

// ---------- 总结库 ----------
function sumCard(it) {
  const s = it.summary;
  const dim = it.status === "skipped" || s?.verdict === "none";
  const text = it.status === "skipped" ? `跳过：${it.skip_reason || ""}` : s?.one_line || "";
  return `<article class="card sum-card ${dim ? "dim" : ""}" data-open="${it.id}">
    <div class="top"><span class="plat ${it.platform}">${PLATFORM[it.platform] || ""}</span><span>${esc(it.uploader || "")}</span><span>${fmtDur(it.duration)}</span>
      ${it.status === "skipped" ? pill("skipped") : verdictPill(s?.verdict)}</div>
    <h3>${esc(it.title)}</h3><p>${esc(text)}</p></article>`;
}
function viewLibrary() {
  const f = state.lib;
  const seg = (key, opts) => `<div class="seg" data-lib="${key}">${opts.map(([k, l]) => `<button data-v="${k}" class="${f[key] === k ? "on" : ""}">${l}</button>`).join("")}</div>`;
  return `
    <div class="page-head"><div><h1>总结库</h1><p>所有处理过的视频。被跳过的也留着，说明了为什么跳过。</p></div></div>
    <div class="toolbar">
      <div class="search">${ICON.search}<input class="input" id="lib-q" placeholder="搜标题、UP 主或总结内容" value="${esc(f.q)}"></div>
      ${seg("verdict", [["all", "全部"], ["essence", "有干货"], ["some", "少量"], ["none", "没精华"], ["skipped", "已跳过"]])}
      ${seg("platform", [["all", "全部平台"], ["bilibili", "B站"], ["douyin", "抖音"], ["local", "本地"]])}
    </div>
    <div id="lib-grid"></div>`;
}
function renderLibGrid() {
  const f = state.lib, q = f.q.toLowerCase();
  const list = state.library.filter((it) => {
    if (f.platform !== "all" && it.platform !== f.platform) return false;
    if (f.verdict === "skipped" && it.status !== "skipped") return false;
    if (!["all", "skipped"].includes(f.verdict) && (it.status !== "done" || it.summary?.verdict !== f.verdict)) return false;
    if (q && ![it.title, it.uploader, it.summary?.one_line, ...(it.summary?.points || []).map((p) => p.text)].join(" ").toLowerCase().includes(q)) return false;
    return true;
  });
  $("#lib-grid").innerHTML = list.length ? `<div class="grid">${list.map(sumCard).join("")}</div>` : `<div class="card empty"><b>没有符合条件的总结</b>换个筛选试试</div>`;
}
function bindLibrary() {
  $("#lib-q").oninput = (e) => { state.lib.q = e.target.value; renderLibGrid(); };
  document.querySelectorAll("[data-lib]").forEach((seg) => (seg.onclick = (e) => {
    const b = e.target.closest("[data-v]");
    if (!b) return;
    state.lib[seg.dataset.lib] = b.dataset.v;
    seg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    renderLibGrid();
  }));
  bindLive($("#lib-grid"));
  renderLibGrid();
}

// ---------- 设置 ----------
function viewSettings() {
  const s = state.settings || {};
  const r = s.skip_rules || {};
  const acc = state.status?.accounts || {};
  const sw = (id, on) => `<span class="switch"><input type="checkbox" id="${id}" ${on ? "checked" : ""}><span></span></span>`;
  const segOpt = (id, cur, opts) => `<div class="seg" data-set="${id}">${opts.map(([k, l]) => `<button data-v="${k}" class="${cur === k ? "on" : ""}">${l}</button>`).join("")}</div>`;
  const account = (k, icon) => {
    const a = acc[k] || {};
    return `<div class="account"><div class="ico ${icon}">${ICON[icon]}</div>
      <div class="grow"><b>${PLATFORM[k]}</b><small>${a.logged_in ? `已登录${a.name && a.name !== "已登录" ? " · " + esc(a.name) : ""}` : "未登录，读取稍后再看需要登录"}</small></div>
      <button class="btn sm" data-login="${k}">${a.logged_in ? "重新登录" : "登录"}</button></div>`;
  };
  return `
    <div class="page-head"><div><h1>设置</h1><p>大部分情况下用默认值就好。</p></div></div>
    <div class="settings">
      <section class="card">
        <h3>账号</h3><p class="desc">只用来读取你自己的稍后再看列表和视频，登录信息只存在这台电脑上。</p>
        ${account("bilibili", "bili")}${account("douyin", "douyin")}
      </section>

      <section class="card">
        <h3>提炼方式</h3><p class="desc">决定总结写多少、什么样的视频直接跳过。</p>
        <div class="field" style="margin-bottom:14px"><label>总结风格</label>
          ${segOpt("summary_style", s.summary_style, [["essence", "只要精华"], ["detailed", "详细要点"], ["brief", "一句话"]])}
          <span class="hint">“只要精华”：没有值得记的内容就直接写“没有精华”，不硬凑。</span></div>
        <div class="toggle-row"><div><div class="t">自动跳过没价值的视频</div><div class="hint">跳过的视频会留在总结库里，写明原因，也可以手动“仍然总结”。</div></div>${sw("auto_skip", s.auto_skip)}</div>
        <div class="toggle-row"><div><div class="t">跳过没有分析内容的纯音乐（保留有信息的画面演示）</div></div>${sw("rule_music", r.music)}</div>
        <div class="toggle-row"><div><div class="t">跳过以带货、口播广告为主的视频</div></div>${sw("rule_ads", r.ads)}</div>
        <div class="toggle-row"><div><div class="t">跳过短于这个时长的视频</div><div class="hint">单位：秒，填 0 表示不按时长跳过</div></div>
          <input class="input" id="rule_min" type="number" min="0" step="5" value="${r.min_seconds ?? 45}" style="width:90px"></div>
      </section>

      <section class="card">
        <h3>听写与长视频</h3><p class="desc">没有字幕的视频会在本机用显卡听写。超长视频按段处理，某段失败只重做那一段。</p>
        <div class="form-grid">
          <div class="field"><label>听写模型</label>
            <select class="input" id="asr_model">${[["large-v3-turbo", "large-v3-turbo（推荐，快且准）"], ["large-v3", "large-v3（更准，更慢更吃显存）"], ["medium", "medium（显存紧张时用）"], ["small", "small（最省资源）"]].map(([k, l]) => `<option value="${k}" ${s.asr_model === k ? "selected" : ""}>${l}</option>`).join("")}</select></div>
          <div class="field"><label>运行设备</label>${segOpt("device", s.device, [["auto", "自动"], ["cuda", "显卡"], ["cpu", "CPU"]])}
            <span class="hint">自动：显存不够时先缩小分段，再退回 CPU。</span></div>
          <div class="field"><label>语言</label>${segOpt("language", s.language, [["auto", "自动识别"], ["zh", "中文"], ["en", "英文"]])}</div>
          <div class="field"><label>长视频每段时长（分钟）</label><input class="input" id="chunk_minutes" type="number" min="2" max="60" value="${s.chunk_minutes ?? 10}">
            <span class="hint">越小越稳，越大越快。</span></div>
          <div class="field"><label>同时处理几条</label>${segOpt("max_parallel", String(s.max_parallel ?? 1), [["1", "1 条"], ["2", "2 条"], ["3", "3 条"]])}
            <span class="hint">听写占显卡，8 GB 显存建议 1 条。</span></div>
          <div class="field"><label>文字稿保存位置</label><input class="input" id="output_dir" value="${esc(s.output_dir || "")}"></div>
        </div>
      </section>

      <div class="save-bar"><button class="btn primary" id="save-settings">保存设置</button></div>
    </div>`;
}
function bindSettings() {
  document.querySelectorAll("[data-set]").forEach((seg) => (seg.onclick = (e) => {
    const b = e.target.closest("[data-v]");
    if (!b) return;
    seg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
  }));
  document.querySelectorAll("[data-login]").forEach((b) => (b.onclick = () => login(b.dataset.login)));
  $("#save-settings").onclick = async () => {
    const segVal = (k) => $(`[data-set="${k}"] .on`)?.dataset.v;
    const next = {
      summary_style: segVal("summary_style"), device: segVal("device"), language: segVal("language"),
      max_parallel: Number(segVal("max_parallel")), asr_model: $("#asr_model").value,
      chunk_minutes: Number($("#chunk_minutes").value), output_dir: $("#output_dir").value.trim(),
      auto_skip: $("#auto_skip").checked,
      skip_rules: { ...(state.settings?.skip_rules || {}), music: $("#rule_music").checked, ads: $("#rule_ads").checked, min_seconds: Number($("#rule_min").value) },
    };
    try { state.settings = await Api.saveSettings(next); toast("设置已保存"); } catch (e) { toast(e.message || "保存失败"); }
  };
}
async function login(platform) {
  try {
    const r = await Api.login(platform);
    if (r.import_cookies) {
      const picker=document.createElement('input'); picker.type='file'; picker.accept='.txt';
      picker.onchange=async()=>{
        const file=picker.files[0]; if(!file) return;
        if(file.size>200000) return toast('请选择小于200KB的Netscape登录文件');
        try {
          const result=await fetch('/api/accounts/douyin/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:await file.text()})});
          const data=await result.json(); toast(data.message || '导入失败');
        } catch { toast('本机登录文件导入失败'); }
      };
      picker.click();
    }
    if (r.qr_image) {
      const dialog = document.createElement('dialog');
      const title = document.createElement('p'); title.textContent = r.message;
      const image = document.createElement('img'); image.src = r.qr_image; image.alt = 'B站登录二维码'; image.width = 260;
      const note = document.createElement('p'); note.textContent = '二维码约3分钟有效。手机确认后可关闭；过期请关闭并重新点击登录。';
      const close = document.createElement('button'); close.className = 'btn'; close.textContent = '关闭'; close.onclick = () => dialog.close();
      dialog.append(title,image,note,close); document.body.append(dialog);
      dialog.addEventListener('close',()=>dialog.remove(),{once:true}); dialog.showModal();
    }
    toast(r.message || (r.ok ? "登录成功" : "登录未完成"));
    state.status = await Api.status();
    renderSys();
  } catch (e) { toast(e.message || "登录失败"); }
}

// ---------- 详情抽屉 ----------
async function openDrawer(id) {
  state.drawer = { id, tab: "summary", data: null, q: "" };
  const d = $("#drawer");
  d.innerHTML = `<div class="empty" style="margin-top:30vh"><span class="spinner" style="display:inline-block"></span></div>`;
  d.classList.add("open");
  d.setAttribute("aria-hidden", "false");
  $("#drawer-backdrop").hidden = false;
  try {
    state.drawer.data = await Api.item(id);
    const st = state.drawer.data.status;
    if (st !== "done") state.drawer.tab = st === "skipped" ? "summary" : "progress";
    renderDrawer();
  } catch (e) {
    d.innerHTML = `<div class="empty"><b>打不开这条</b>${esc(e.message || "")}</div>`;
  }
}
function closeDrawer() {
  $("#drawer").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
  $("#drawer-backdrop").hidden = true;
  state.drawer.id = null;
}
function renderDrawer() {
  const it = state.drawer.data;
  if (!it) return;
  const tabs = [["summary", "精华"], ["transcript", "原文"], ["progress", "处理过程"]];
  $("#drawer").innerHTML = `
    <div class="drawer-head">
      <div class="row"><span class="plat ${it.platform}">${PLATFORM[it.platform] || ""}</span>${pill(it.status)}
        <button class="btn ghost sm close" id="drawer-close" aria-label="关闭">${ICON.x}</button></div>
      <h2>${esc(it.title)}</h2>
      <div class="meta">${it.uploader ? `<span>${esc(it.uploader)}</span>` : ""}<span>时长 ${fmtDur(it.duration)}</span>${it.source ? `<span>正文来自${esc(it.source)}</span>` : ""}</div>
    </div>
    <div class="drawer-tabs">${tabs.map(([k, l]) => `<button data-tab="${k}" class="${state.drawer.tab === k ? "on" : ""}">${l}</button>`).join("")}</div>
    <div class="drawer-body" id="drawer-body">${drawerBody(it)}</div>
    <div class="drawer-foot">
      ${it.url ? `<a class="btn" href="${esc(it.url)}" target="_blank" rel="noopener">${ICON.open}打开原视频</a>` : ""}
      ${it.status === "done" ? `<button class="btn" id="copy-md">${ICON.copy}复制总结</button>` : ""}
      ${it.status === "skipped" || it.summary?.verdict === "none" ? `<button class="btn primary" id="force-sum">仍然总结</button>` : ""}
      ${it.status === "failed" ? `<button class="btn primary" id="retry-one">${ICON.retry}重试</button>` : ""}
      ${it.status === "running" || it.status === "queued" ? `<button class="btn" id="cancel-one">取消这条</button>` : ""}
    </div>`;
  $("#drawer-close").onclick = closeDrawer;
  document.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => { state.drawer.tab = b.dataset.tab; renderDrawer(); }));
  $("#copy-md") && ($("#copy-md").onclick = () => copyText(toMarkdown(it)));
  $("#force-sum") && ($("#force-sum").onclick = async () => { await Api.summarizeAnyway(it.id); toast("已重新排队，这次不会跳过"); closeDrawer(); refreshBatches(); });
  $("#retry-one") && ($("#retry-one").onclick = async () => { await Api.retry(it.id); toast("已重新排队"); closeDrawer(); refreshBatches(); });
  $("#cancel-one") && ($("#cancel-one").onclick = async () => { await Api.cancel(it.id); toast("已取消"); closeDrawer(); refreshBatches(); });
  const q = $("#tx-q");
  if (q) q.oninput = (e) => { state.drawer.q = e.target.value; $("#tx").innerHTML = transcriptLines(it); };
}
function drawerBody(it) {
  const tab = state.drawer.tab;
  if (tab === "progress") return progressBody(it);
  if (tab === "transcript") {
    if (!it.transcript?.length) return `<div class="empty"><b>还没有原文</b>拿到字幕或听写完成后会显示在这里</div>`;
    return `<input class="input tx-search" id="tx-q" placeholder="在原文里搜索" value="${esc(state.drawer.q)}"><div class="tx" id="tx">${transcriptLines(it)}</div>`;
  }
  if (it.status === "skipped") {
    return `<div class="verdict-box none"><div><div class="v-label">已跳过</div><div class="v-text">${esc(it.skip_reason || "")}</div></div></div>
      <div class="note">判断错了？点下面的“仍然总结”，这条会重新处理且不会再被跳过。</div>`;
  }
  const s = it.summary;
  if (!s) return `<div class="empty"><b>还在处理</b>完成后精华会出现在这里。<br><button class="link" data-tab-go="progress">看处理过程</button></div>`;
  return `
    <div class="verdict-box ${s.verdict}"><div><div class="v-label">${VERDICT[s.verdict]}</div><div class="v-text">${esc(s.one_line)}</div></div></div>
    ${s.points?.length ? `<div class="block"><h4>精华</h4><ul class="points">${s.points.map((p) => `<li class="${p.t == null ? "no-t" : ""}">${p.t != null ? timeLink(it, p.t) : ""}<span>${esc(p.text)}</span></li>`).join("")}</ul></div>` : ""}
    ${s.highlights?.length ? `<div class="block"><h4>值得回看</h4><ul class="points">${s.highlights.map((p) => `<li>${timeLink(it, p.t)}<span>${esc(p.text)}</span></li>`).join("")}</ul></div>` : ""}
    ${s.audience ? `<div class="block"><h4>适合谁</h4><div class="note">${esc(s.audience)}</div></div>` : ""}
    ${s.skip_note ? `<div class="block"><h4>备注</h4><div class="note">${esc(s.skip_note)}</div></div>` : ""}
    ${it.source === "听写" ? `<div class="hint" style="font-size:12px;color:var(--text-3)">正文由语音听写得到，专有名词可能有错字。</div>` : ""}`;
}
function transcriptLines(it) {
  const q = state.drawer.q.trim();
  const re = q ? new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi") : null;
  const lines = it.transcript.filter((l) => !re || re.test(l.text));
  if (!lines.length) return `<div class="empty">原文里没有“${esc(q)}”</div>`;
  return lines.map((l) => {
    let text = esc(l.text);
    if (re) text = text.replace(new RegExp(esc(q).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), (m) => `<mark>${m}</mark>`);
    return `<div class="tx-line">${timeLink(it, l.start)}<span>${text}</span></div>`;
  }).join("");
}
function progressBody(it) {
  const si = it.status === "done" ? STAGES.length : stageIndex(it.stage);
  const rows = STAGES.map(([k, label], i) => {
    let cls = "", dot = "", right = "";
    if (it.status === "skipped" && i === si) { cls = "done"; dot = ICON.skip; right = "在这一步跳过"; }
    else if (it.status === "failed" && i === si) { cls = "bad"; dot = ICON.x; right = "失败"; }
    else if (i < si || it.status === "done") { cls = "done"; dot = ICON.check; }
    else if (i === si && it.status === "running") { cls = "now"; dot = '<span class="spinner" style="width:12px;height:12px"></span>'; right = `${Math.round(it.progress * 100)}%`; }
    let sub = "";
    if (k === "content" && it.chunk && (i <= si)) {
      sub = `<div class="chunks">${Array.from({ length: it.chunk.total }, (_, n) => `<i class="${n + 1 < it.chunk.index || (it.status !== "running" && i < si) ? "done" : n + 1 === it.chunk.index && it.status === "running" && i === si ? "now" : ""}"></i>`).join("")}</div>
        <small>共 ${it.chunk.total} 段${it.status === "running" && i === si ? `，正在第 ${it.chunk.index} 段` : ""}</small>`;
    }
    return `<div class="stage ${cls}"><div class="s-dot">${dot}</div><div>${label}${sub}</div><small>${right}</small></div>`;
  }).join("");
  return `
    <div class="block"><div class="stage-list">${rows}</div></div>
    ${it.status === "running" ? `<div class="note">${esc(it.message || "")}${it.eta_sec != null ? `，${fmtEta(it.eta_sec)}后完成` : ""}</div>` : ""}
    ${it.error ? `<div class="block"><h4>出错原因</h4><div class="note" style="color:var(--bad)">${esc(it.error)}</div></div>` : ""}
    ${it.log?.length ? `<div class="block" style="margin-top:20px"><h4>日志</h4><div class="log">${esc(it.log.join("\n"))}</div></div>` : ""}`;
}
function toMarkdown(it) {
  const s = it.summary || {};
  const t = (p) => (p.t != null ? `[${fmtDur(p.t)}] ` : "");
  return [
    `# ${it.title}`, `${PLATFORM[it.platform] || ""} · ${it.uploader || ""} · ${fmtDur(it.duration)}${it.url ? ` · ${it.url}` : ""}`, "",
    `**${VERDICT[s.verdict] || ""}**：${s.one_line || ""}`, "",
    ...(s.points?.length ? ["## 精华", ...s.points.map((p) => `- ${t(p)}${p.text}`), ""] : []),
    ...(s.highlights?.length ? ["## 值得回看", ...s.highlights.map((p) => `- ${t(p)}${p.text}`), ""] : []),
    ...(s.audience ? ["## 适合谁", s.audience] : []),
  ].join("\n");
}
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast("已复制为 Markdown"); }
  catch { toast("复制失败，浏览器没给剪贴板权限"); }
}

// ---------- 路由与数据 ----------
const VIEWS = {
  home: [viewHome, bindHome],
  queue: [viewQueue, bindQueue],
  library: [viewLibrary, bindLibrary],
  settings: [viewSettings, bindSettings],
};
async function go(view) {
  state.view = view;
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  if (view === "library") state.library = await Api.library().catch(() => []);
  if (view === "settings") state.settings = await Api.settings().catch(() => state.settings);
  renderView();
  window.scrollTo(0, 0);
}
function renderView() {
  const [view, bind] = VIEWS[state.view];
  $("#view").innerHTML = view();
  bind();
}
function renderLive() {
  renderNavBadge();
  if (state.view === "home") renderHomeLive();
  if (state.view === "queue") renderQueueList();
}
// 进行中的批次排前面，其余按创建时间从新到旧
function sortBatches(list) {
  const live = (b) => (b.counts.running || b.counts.queued ? 1 : 0);
  return [...list].sort((a, b) => live(b) - live(a) || new Date(b.created_at) - new Date(a.created_at));
}
async function refreshBatches() {
  state.batches = sortBatches(await Api.batches().catch(() => state.batches));
  renderLive();
}

let liveTimer;
function onEvent(ev) {
  if (ev.type === "refresh" && ev.batches) state.batches = sortBatches(ev.batches);
  if (ev.type === "item" && ev.item) {
    for (const b of state.batches) {
      const i = b.items.findIndex((x) => x.id === ev.item.id);
      if (i >= 0) {
        b.items[i] = ev.item;
        const c = { done: 0, skipped: 0, failed: 0, running: 0, queued: 0, canceled: 0 };
        b.items.forEach((x) => (c[x.status] = (c[x.status] || 0) + 1));
        b.counts = c;
      }
    }
    if (state.drawer.id === ev.item.id && state.drawer.data) {
      const wasDone = state.drawer.data.status === "done";
      Object.assign(state.drawer.data, ev.item);
      if (!wasDone && ev.item.status === "done") {
        Api.item(ev.item.id).then((d) => { state.drawer.data = d; state.drawer.tab = "summary"; renderDrawer(); });
      } else if (state.drawer.tab === "progress") $("#drawer-body").innerHTML = progressBody(state.drawer.data);
    }
  }
  if (ev.type === "batch") return refreshBatches();
  // 合并高频事件，避免每条推送都重绘
  clearTimeout(liveTimer);
  liveTimer = setTimeout(renderLive, 80);
}

async function boot() {
  try {
    const t = localStorage.getItem("theme");
    if (t && t !== "auto") document.documentElement.dataset.theme = t;
  } catch {}
  await Api.detect();
  $("#mock-banner").hidden = Api.mode !== "mock";
  [state.status, state.batches] = await Promise.all([Api.status().catch(() => null), Api.batches().catch(() => [])]);
  state.batches = sortBatches(state.batches);
  renderSys();
  renderNavBadge();
  $("#nav").onclick = (e) => { const b = e.target.closest("[data-view]"); if (b) go(b.dataset.view); };
  $("#drawer-backdrop").onclick = closeDrawer;
  $("#drawer").addEventListener("click", (e) => {
    const t = e.target.closest("[data-tab-go]");
    if (t) { state.drawer.tab = t.dataset.tabGo; renderDrawer(); }
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && state.drawer.id) closeDrawer(); });
  Api.subscribe(onEvent);
  setInterval(async () => { state.status = await Api.status().catch(() => state.status); renderSys(); }, 5000);
  go(location.hash.slice(1) in VIEWS ? location.hash.slice(1) : "home");
}
boot();
