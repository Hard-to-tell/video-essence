// 演示用的假后端：实现与真实后端相同的接口（见 docs/界面交接-Codex.md），
// 用定时器模拟进度，让界面在后端没接上时也能完整预览。真实后端接好后不会被加载。
(function () {
  const now = () => Date.now();
  let seq = 100;
  const id = (p) => `${p}_${++seq}`;

  const SUMMARIES = [
    {
      verdict: "essence",
      one_line: "3DGS 用大量可优化的椭球表示场景，入门只需 Postshot 训练 + SuperSplat 编辑，30 分钟出第一个模型。",
      points: [
        { t: 63, text: "3DGS 由两部分组成：一种三维表征（每个高斯有位置、颜色、透明度、缩放、旋转）和一种可微的光栅化渲染。" },
        { t: 246, text: "训练本质是把渲染图和真实照片做对比，反复调整每个高斯的参数，所以照片质量直接决定上限。" },
        { t: 314, text: "SuperSplat 能在网页里直接看和编辑 .ply，删杂点用框选比逐个点快得多。" },
        { t: 568, text: "球谐阶数越高颜色越真，但显存和文件体积会明显上涨，普通展示用 1 到 2 阶够了。" },
        { t: 600, text: "Postshot 一键完成相机位姿估计和训练，默认 3 万轮；缺点是订阅费每月 200 多元。" },
      ],
      highlights: [
        { t: 314, text: "SuperSplat 编辑演示，2 分钟看懂怎么清理模型" },
        { t: 600, text: "Postshot 完整训练流程" },
      ],
      audience: "想上手 3D 重建或摄影新玩法的人；已经懂 NeRF 的可以跳过前 4 分钟。",
    },
    {
      verdict: "some",
      one_line: "核心只有一条：早起有用的前提是睡够，其余是作者个人作息的流水账。",
      points: [
        { t: 95, text: "固定起床时间比固定入睡时间更容易坚持，周末也不要差超过 1 小时。" },
        { t: 410, text: "起床后 30 分钟内晒到自然光，对调整生物钟最有效。" },
      ],
      highlights: [],
      audience: "作息混乱想调整的人。只看上面两条即可，不必看完。",
    },
    {
      verdict: "none",
      one_line: "没有精华：整段是产品开箱和外观展示，没有给出可用的信息或结论。",
      points: [],
      highlights: [],
      audience: "",
      skip_note: "如果你只是想看外观，原视频 1 分钟内就能看完。",
    },
    {
      verdict: "essence",
      one_line: "面试被问“你的缺点”时，讲一个真实但与岗位核心能力无关的缺点，并给出你正在用的具体改进方法。",
      points: [
        { t: 32, text: "别说“我太追求完美”，面试官听了几百遍，会直接扣分。" },
        { t: 88, text: "结构：真实缺点 → 一次具体的后果 → 现在的改进做法 → 改进后的结果。" },
        { t: 151, text: "缺点不能落在岗位核心能力上，比如应聘数据分析就别说“对数字不敏感”。" },
      ],
      highlights: [{ t: 88, text: "四段式回答模板" }],
      audience: "近期要面试的人。",
    },
  ];

  const TRANSCRIPT = [
    [0, "你现在看到的不是现实拍摄的视频，也不是 CG，而是 3D 高斯带来的视觉奇迹。"],
    [30, "这一期视频我们会首先讲解 3D 高斯的基本原理，我会用最简单的话来讲解它的训练框架。"],
    [63, "第一个部分是一种三维表征，这种三维表征定义了 3D 高斯本身；第二个是一种渲染技术。"],
    [125, "下面对应了它的参数，首先是 XYZ，这跟点云是一样的，然后是三个 DC，它决定了颜色。"],
    [155, "还有一个 opacity 表明它的不透明度，还有 scale 表明每个高斯在每个轴上的大小。"],
    [246, "那如何让高斯正确地渲染出我们想要的图像呢？这就需要对高斯进行优化。"],
    [314, "SuperSplat 可以支持你直接在 Web 端查看 3D 高斯，并且这个查看的体验是非常丝滑的。"],
    [505, "如果我们一次性想删除更多的东西，可以选择框选，把它拉出来就可以删除。"],
    [568, "这里是球谐函数的阶数，阶数越高渲染出来的效果就越好，但是占用的内存会更多。"],
    [600, "接下来我们讲一下怎么样去训练自己的高斯，来到 Postshot 的网址，点击 Download。"],
    [728, "而且非常的昂贵，一个月要 200 多块钱，所以如果公司可以报销的话我推荐你来使用它。"],
  ].map(([t, text]) => ({ start: t, end: t + 28, text }));

  const COLORS = ["#7c6cf0", "#e0699a", "#2f9e8f", "#d98b2b", "#4b7bd8", "#9c5bd1", "#3a9b5c", "#c4554d"];

  function mkItem(batch, platform, title, uploader, duration, state) {
    const it = {
      id: id("item"), batch_id: batch, platform, title, uploader, duration,
      url: platform === "bilibili" ? "https://www.bilibili.com/video/BV1GKinBiEhJ/" : "https://www.douyin.com/video/7300000000000000000",
      cover: null, color: COLORS[seq % COLORS.length],
      added_at: new Date(now() - 3600e3 * Math.random() * 30).toISOString(),
      status: "queued", stage: null, progress: 0, chunk: null, eta_sec: null,
      message: "", source: null, skip_reason: null, error: null, summary: null, log: [],
    };
    Object.assign(it, state || {});
    return it;
  }

  const store = { batches: [], items: {} };
  const listeners = new Set();
  const emit = (ev) => listeners.forEach((fn) => fn(ev));

  function addBatch(b, items) {
    store.batches.unshift(b);
    b.item_ids = items.map((i) => i.id);
    items.forEach((i) => (store.items[i.id] = i));
  }

  // 预置：一批正在跑的抖音稍后再看 + 一批已完成的 B 站
  (function seed() {
    const b1 = { id: id("batch"), title: "抖音 · 稍后再看", platform: "douyin", kind: "watch_later", created_at: new Date(now() - 6 * 60e3).toISOString(), auto_skip: true };
    const d = (s, extra) => mkItem(b1.id, "douyin", s[0], s[1], s[2], extra);
    const items1 = [
      d(["面试被问缺点怎么答？HR 不会告诉你的回答模板", "职场老陈", 212], { status: "done", stage: "done", progress: 1, source: "字幕", summary: SUMMARIES[3] }),
      d(["开箱！这台相机的手感也太好了吧", "数码小鹿", 58], { status: "skipped", stage: "judge", progress: 1, skip_reason: "开箱和外观展示，没有可提炼的信息" }),
      d(["每天 5 点起床坚持 100 天，我的变化", "早起的阿雅", 486], { status: "done", stage: "done", progress: 1, source: "听写", summary: SUMMARIES[1] }),
      d(["这首歌前奏一响就破防了", "音乐收藏夹", 41], { status: "skipped", stage: "meta", progress: 1, skip_reason: "纯音乐，没有口语内容" }),
      d(["一口气讲清楚美联储降息对普通人的影响", "财经老王说", 1985], { status: "running", stage: "content", progress: 0.42, source: "听写", chunk: { index: 4, total: 9 }, eta_sec: 96, message: "GPU 听写第 4/9 段" }),
      d(["三分钟学会手冲咖啡的三个关键变量", "豆子研究所", 192]),
      d(["上海 citywalk 路线，周末去不踩雷", "城市漫游指南", 334]),
      d(["这个 Excel 技巧让我每天少加班一小时", "表哥办公", 147]),
    ];
    addBatch(b1, items1);

    const b2 = { id: id("batch"), title: "B 站 · 稍后再看", platform: "bilibili", kind: "watch_later", created_at: new Date(now() - 26 * 3600e3).toISOString(), auto_skip: true };
    const items2 = [
      mkItem(b2.id, "bilibili", "3D高斯第1期：十分钟从认识3D高斯到开始训练", "重建世界LAB", 767, { status: "done", stage: "done", progress: 1, source: "听写", summary: SUMMARIES[0] }),
      mkItem(b2.id, "bilibili", "【4K】雨天的东京街头 · 无人声白噪音", "慢镜头", 3600, { status: "skipped", stage: "meta", progress: 1, skip_reason: "无人声的氛围视频，没有内容可提炼" }),
      mkItem(b2.id, "bilibili", "一小时讲透 Transformer：从注意力到 GPT", "跟李沐学AI", 5410, { status: "failed", stage: "content", progress: 0.3, error: "显存不足（CUDA out of memory），已尝试缩小分段仍失败", chunk: { index: 6, total: 20 } }),
    ];
    addBatch(b2, items2);
  })();

  function batchView(b) {
    const items = b.item_ids.map((i) => store.items[i]);
    const count = (s) => items.filter((i) => i.status === s).length;
    return {
      ...b,
      total: items.length,
      counts: { done: count("done"), skipped: count("skipped"), failed: count("failed"), running: count("running"), queued: count("queued"), canceled: count("canceled") },
      items: items.map(itemLite),
    };
  }
  const itemLite = (i) => { const { log, ...rest } = i; return rest; };

  // ---- 模拟器：每个批次同一时间只跑一条 ----
  const STAGE_SPEED = { meta: 0.25, content: 0.06, judge: 0.35, summarize: 0.12 };
  function tick() {
    for (const b of store.batches) {
      const items = b.item_ids.map((i) => store.items[i]);
      let run = items.find((i) => i.status === "running");
      if (!run) {
        run = items.find((i) => i.status === "queued");
        if (!run) continue;
        Object.assign(run, { status: "running", stage: "meta", progress: 0, message: "读取视频信息" });
        run.log.push(`${time()} 开始：${run.title}`);
      }
      step(run, b);
      emit({ type: "item", item: itemLite(run) });
    }
  }
  function time() { return new Date().toTimeString().slice(0, 8); }
  function step(it, b) {
    const sp = STAGE_SPEED[it.stage] || 0.1;
    it.progress = Math.min(1, it.progress + sp * (0.6 + Math.random() * 0.8));
    if (it.stage === "content" && it.chunk) {
      it.chunk.index = Math.min(it.chunk.total, Math.max(1, Math.ceil(it.progress * it.chunk.total)));
      it.message = `${it.source === "字幕" ? "整理字幕" : "GPU 听写"}第 ${it.chunk.index}/${it.chunk.total} 段`;
      it.eta_sec = Math.round((1 - it.progress) * it.duration * 0.12);
    }
    if (it.progress < 1) return;
    it.progress = 0;
    if (it.stage === "meta") {
      if (b.auto_skip && it.duration < 60 && Math.random() < 0.5) return finish(it, "skipped", "太短且没有口语内容");
      const subs = Math.random() < 0.35;
      Object.assign(it, { stage: "content", source: subs ? "字幕" : "听写", chunk: { index: 1, total: Math.max(1, Math.ceil(it.duration / 240)) } });
      it.log.push(`${time()} ${subs ? "找到字幕，抽样核对通过" : "没有字幕，下载音频后听写"}，共 ${it.chunk.total} 段`);
    } else if (it.stage === "content") {
      Object.assign(it, { stage: "judge", message: "判断有没有值得提炼的内容", eta_sec: 8 });
    } else if (it.stage === "judge") {
      if (b.auto_skip && Math.random() < 0.2) return finish(it, "skipped", "内容以带货/口播广告为主，没有可提炼的信息");
      Object.assign(it, { stage: "summarize", message: "提炼精华", eta_sec: 15 });
    } else if (it.stage === "summarize") {
      it.summary = SUMMARIES[Math.floor(Math.random() * SUMMARIES.length)];
      finish(it, "done");
    }
  }
  function finish(it, status, reason) {
    Object.assign(it, { status, progress: 1, message: "", eta_sec: null });
    if (status === "done") it.stage = "done";
    if (reason) it.skip_reason = reason;
    it.log.push(`${time()} ${status === "done" ? "完成" : "跳过：" + reason}`);
  }
  setInterval(tick, 700);

  // ---- 路由 ----
  const SAMPLE_TITLES = [
    ["为什么你总是存不下钱？三个反直觉的建议", "理财小白课", 402],
    ["猫咪的这些行为其实是在求救", "宠物医生小林", 268],
    ["Python 自动化办公：10 行代码批量改文件名", "码农阿杰", 515],
    ["今天又是被老板夸的一天（剧情）", "办公室日常", 73],
    ["读完《穷查理宝典》我只记住了这 5 句话", "书单精读", 731],
  ];

  let settings = {
    asr_model: "large-v3-turbo", device: "auto", language: "auto",
    chunk_minutes: 10, max_parallel: 1, auto_skip: true,
    skip_rules: { min_seconds: 45, music: true, ads: true, no_speech: true },
    summary_style: "essence", output_dir: "transcripts",
  };

  const routes = [
    ["GET", /^\/api\/status$/, () => ({
      backend: "mock", version: "demo",
      gpu: { name: "RTX 5060", mem_used_mb: 2860 + Math.round(Math.random() * 400), mem_total_mb: 8151 },
      model: settings.asr_model,
      accounts: { bilibili: { logged_in: true, name: "已登录" }, douyin: { logged_in: false } },
      running: Object.values(store.items).filter((i) => i.status === "running").length,
    })],
    ["GET", /^\/api\/batches$/, () => store.batches.map(batchView)],
    ["GET", /^\/api\/items\/([^/]+)$/, (m) => {
      const it = store.items[m[1]];
      if (!it) throw { status: 404, message: "找不到这条视频" };
      return { ...it, transcript: it.status === "done" || it.status === "skipped" ? TRANSCRIPT : [] };
    }],
    ["GET", /^\/api\/library$/, () => Object.values(store.items)
      .filter((i) => i.status === "done" || i.status === "skipped")
      .map(itemLite)],
    ["POST", /^\/api\/jobs$/, (m, body) => {
      const platform = body.platform || "bilibili";
      const titles = {
        watch_later: platform === "douyin" ? "抖音 · 稍后再看" : "B 站 · 稍后再看",
        links: "粘贴的链接", files: "本地文件", prompt: body.prompt || "一句话任务",
      };
      const b = { id: id("batch"), title: titles[body.kind] || "新任务", platform, kind: body.kind, created_at: new Date().toISOString(), auto_skip: body.auto_skip !== false };
      let src = SAMPLE_TITLES;
      if (body.kind === "links") src = body.links.map((u, i) => [`链接 ${i + 1}：${u.replace(/^https?:\/\//, "").slice(0, 40)}`, "", 300 + i * 120]);
      if (body.kind === "files") src = body.files.map((f) => [f, "", 900]);
      const n = body.kind === "watch_later" || body.kind === "prompt" ? Math.min(body.limit || 5, src.length) : src.length;
      const items = src.slice(0, n).map((s) => mkItem(b.id, body.kind === "files" ? "local" : platform, s[0], s[1], s[2]));
      addBatch(b, items);
      emit({ type: "batch", batch: batchView(b) });
      return { batch_id: b.id };
    }],
    ["POST", /^\/api\/items\/([^/]+)\/(retry|cancel|summarize)$/, (m) => {
      const it = store.items[m[1]];
      if (!it) throw { status: 404, message: "找不到这条视频" };
      if (m[2] === "cancel") Object.assign(it, { status: "canceled", message: "", eta_sec: null });
      else Object.assign(it, { status: "queued", stage: null, progress: 0, error: null, skip_reason: null, summary: null, chunk: null, force: m[2] === "summarize" });
      emit({ type: "item", item: itemLite(it) });
      return { ok: true };
    }],
    ["POST", /^\/api\/batches\/([^/]+)\/cancel$/, (m) => {
      const b = store.batches.find((x) => x.id === m[1]);
      b.item_ids.forEach((i) => { const it = store.items[i]; if (it.status === "queued" || it.status === "running") it.status = "canceled"; });
      emit({ type: "batch", batch: batchView(b) });
      return { ok: true };
    }],
    ["GET", /^\/api\/settings$/, () => settings],
    ["PUT", /^\/api\/settings$/, (m, body) => (settings = { ...settings, ...body })],
    ["POST", /^\/api\/accounts\/(bilibili|douyin)\/login$/, (m) => ({ ok: false, message: "演示模式：登录由后端实现" })],
  ];

  window.MockBackend = {
    async request(method, path, body) {
      await new Promise((r) => setTimeout(r, 120));
      const p = path.split("?")[0];
      for (const [mth, re, fn] of routes) {
        const m = mth === method && p.match(re);
        if (m) return JSON.parse(JSON.stringify(fn(m, body || {})));
      }
      throw { status: 404, message: `演示后端没有 ${method} ${p}` };
    },
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
  };
})();
