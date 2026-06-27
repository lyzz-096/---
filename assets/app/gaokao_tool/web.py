from __future__ import annotations


def render_app_html() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>高考志愿全自动咨询系统</title>
  <style>
    :root {
      --bg-top: #f3efe4;
      --bg-bottom: #dbe7f2;
      --panel: rgba(255, 255, 255, 0.88);
      --panel-strong: #ffffff;
      --text: #13233a;
      --muted: #56708e;
      --line: rgba(19, 35, 58, 0.12);
      --accent: #0f6cbd;
      --accent-2: #d96c2f;
      --good: #2d7a46;
      --warn: #c17700;
      --safe: #2460a7;
      --shadow: 0 18px 50px rgba(17, 40, 72, 0.14);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(255,255,255,0.85), transparent 28%),
        radial-gradient(circle at 85% 15%, rgba(15,108,189,0.18), transparent 18%),
        linear-gradient(145deg, var(--bg-top), var(--bg-bottom));
    }

    .shell {
      width: min(1180px, calc(100% - 32px));
      margin: 28px auto;
      display: grid;
      grid-template-columns: 420px 1fr;
      gap: 20px;
    }

    .panel {
      background: var(--panel);
      border: 1px solid rgba(255,255,255,0.7);
      box-shadow: var(--shadow);
      border-radius: 24px;
      backdrop-filter: blur(16px);
    }

    .left-panel {
      padding: 24px;
    }

    .brand {
      margin-bottom: 20px;
    }

    .eyebrow {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(15, 108, 189, 0.1);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
    }

    h1 {
      margin: 12px 0 8px;
      font-size: 34px;
      line-height: 1.08;
    }

    .subtitle {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
      font-size: 14px;
    }

    form {
      margin-top: 20px;
      display: grid;
      gap: 12px;
    }

    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }

    label {
      display: grid;
      gap: 6px;
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
    }

    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      font: inherit;
      color: var(--text);
      background: rgba(255, 255, 255, 0.86);
      transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
    }

    textarea {
      min-height: 90px;
      resize: vertical;
    }

    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: rgba(15, 108, 189, 0.45);
      box-shadow: 0 0 0 4px rgba(15, 108, 189, 0.12);
      transform: translateY(-1px);
    }

    .actions {
      display: flex;
      gap: 10px;
      margin-top: 8px;
    }

    button {
      border: 0;
      border-radius: 14px;
      padding: 12px 18px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease;
    }

    button:hover {
      transform: translateY(-1px);
    }

    .primary {
      background: linear-gradient(135deg, var(--accent), #3487d1);
      color: #fff;
      box-shadow: 0 12px 24px rgba(15, 108, 189, 0.22);
    }

    .ghost {
      background: rgba(19, 35, 58, 0.06);
      color: var(--text);
    }

    .hint {
      margin-top: 12px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.6;
    }

    .right-panel {
      padding: 24px;
      display: grid;
      gap: 18px;
      align-content: start;
    }

    .result-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }

    .result-head h2 {
      margin: 0;
      font-size: 22px;
    }

    .status {
      font-size: 13px;
      color: var(--muted);
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(19, 35, 58, 0.06);
    }

    .summary {
      padding: 18px;
      background: var(--panel-strong);
      border-radius: 18px;
      border: 1px solid var(--line);
      white-space: pre-wrap;
      line-height: 1.72;
      font-size: 14px;
    }

    .diagnostics {
      display: none;
      padding: 16px;
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid var(--line);
      border-radius: 18px;
    }

    .diagnostics h3 {
      margin: 0 0 10px;
      font-size: 15px;
    }

    .diagnostics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 10px;
      margin-bottom: 10px;
    }

    .diag-item {
      padding: 10px;
      border-radius: 12px;
      background: rgba(19, 35, 58, 0.05);
      min-height: 68px;
    }

    .diag-label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }

    .diag-value {
      display: block;
      font-size: 18px;
      font-weight: 800;
    }

    .diag-messages {
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.7;
    }

    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }

    .card {
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      box-shadow: 0 10px 22px rgba(17, 40, 72, 0.06);
    }

    .tier {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 10px;
    }

    .tier-冲 {
      background: rgba(217, 108, 47, 0.12);
      color: var(--accent-2);
    }

    .tier-稳 {
      background: rgba(193, 119, 0, 0.12);
      color: var(--warn);
    }

    .tier-保 {
      background: rgba(36, 96, 167, 0.12);
      color: var(--safe);
    }

    .card h3 {
      margin: 0 0 8px;
      font-size: 18px;
      line-height: 1.3;
    }

    .meta {
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 13px;
    }

    .card p {
      margin: 8px 0 0;
      font-size: 13px;
      line-height: 1.65;
    }

    .empty {
      padding: 28px;
      text-align: center;
      color: var(--muted);
      border: 1px dashed rgba(19, 35, 58, 0.18);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.58);
    }

    @media (max-width: 980px) {
      .shell {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 640px) {
      .shell {
        width: min(100% - 20px, 100%);
        margin: 14px auto;
      }

      .grid {
        grid-template-columns: 1fr;
      }

      h1 {
        font-size: 28px;
      }

      .left-panel, .right-panel {
        padding: 18px;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="panel left-panel">
      <div class="brand">
        <span class="eyebrow">GAOKAO AUTO ADVISOR</span>
        <h1>高考志愿全自动咨询系统</h1>
        <p class="subtitle">把咨询追问、冲稳保推荐、联网取证和正式报告导出串成一个可直接演示的本地入口。</p>
      </div>

      <form id="advisor-form">
        <div class="grid">
          <label>省份
            <input name="province" value="" placeholder="如 上海、湖北" required />
          </label>
          <label>科类/选科
            <input name="subject_type" value="" placeholder="如 物理类、历史类、综合" required />
          </label>
        </div>

        <div class="grid">
          <label>分数
            <input name="score" value="" placeholder="如 577" />
          </label>
          <label>位次（可自动匹配）
            <input name="rank" value="" placeholder="可留空，先按分数匹配" />
          </label>
        </div>

        <label>偏好专业
          <input name="preferred_majors" value="" placeholder="如 法学、师范、电气；不填则不限专业" />
        </label>

        <label>排斥专业
          <input name="excluded_majors" value="" placeholder="如 土木；不填则不排除" />
        </label>

        <label>城市偏好
          <input name="preferred_regions" value="" placeholder="如 武汉,宜昌；不填则不限城市" />
        </label>

        <div class="grid">
          <label>核心诉求
            <input name="career_goal" value="" placeholder="如 就业、考公、稳定、深造" />
          </label>
          <label>家庭资源
            <input name="family_background" value="" placeholder="如 普通家庭、电网、医生" />
          </label>
        </div>

        <label>是否接受考研
          <select name="accept_postgraduate">
            <option value="n" selected>不优先</option>
            <option value="y">可以接受</option>
          </select>
        </label>

        <div class="actions">
          <button class="primary" type="submit">生成推荐</button>
          <button class="ghost" type="button" id="export-report">导出正式报告</button>
          <button class="ghost" type="button" id="run-research">执行联网取证</button>
          <button class="ghost" type="button" id="match-rank">按分数匹配位次</button>
          <button class="ghost" type="button" id="fill-demo">计算机演示案例</button>
        </div>

        <div class="hint">
          空白字段会按“未填写”处理，不会套用演示案例或默认偏好。每次查询前都会先确认当前输入。
        </div>
      </form>
    </section>

    <section class="panel right-panel">
      <div class="result-head">
        <h2>推荐结果</h2>
        <div class="status" id="status">等待提交</div>
      </div>

      <div class="summary" id="summary">提交后，这里会显示完整的分析摘要。</div>
      <div class="summary" id="research-summary" style="display: none;"></div>
      <div class="diagnostics" id="diagnostics"></div>
      <div class="cards" id="cards"></div>
      <div class="cards" id="evidence-cards"></div>
      <div class="empty" id="empty">先在左边填一下考生信息，我们就能看到冲、稳、保三档推荐。</div>
    </section>
  </div>

  <script>
    const form = document.getElementById("advisor-form");
    const summary = document.getElementById("summary");
    const researchSummary = document.getElementById("research-summary");
    const diagnostics = document.getElementById("diagnostics");
    const cards = document.getElementById("cards");
    const evidenceCards = document.getElementById("evidence-cards");
    const empty = document.getElementById("empty");
    const status = document.getElementById("status");
    const fillDemo = document.getElementById("fill-demo");
    const matchRank = document.getElementById("match-rank");
    const runResearch = document.getElementById("run-research");
    const exportReport = document.getElementById("export-report");

    const demoValues = {
      province: "湖北",
      subject_type: "物理类",
      score: "580",
      rank: "",
      preferred_majors: "计算机,电子",
      excluded_majors: "土木",
      preferred_regions: "武汉,宜昌",
      career_goal: "就业",
      family_background: "普通家庭",
      accept_postgraduate: "n"
    };

    fillDemo.addEventListener("click", () => {
      for (const [key, value] of Object.entries(demoValues)) {
        const field = form.elements.namedItem(key);
        if (field) {
          field.value = value;
        }
      }
      status.textContent = "已填入演示案例";
    });

    function currentPayload() {
      return Object.fromEntries(new FormData(form).entries());
    }

    function fieldValue(payload, key) {
      const value = (payload[key] || "").trim();
      return value || "未填";
    }

    function describePayload(payload) {
      return [
        "请确认本次查询输入：",
        "",
        "省份：" + fieldValue(payload, "province"),
        "科类/选科：" + fieldValue(payload, "subject_type"),
        "分数：" + fieldValue(payload, "score"),
        "位次：" + fieldValue(payload, "rank"),
        "偏好专业：" + fieldValue(payload, "preferred_majors"),
        "排斥专业：" + fieldValue(payload, "excluded_majors"),
        "城市偏好：" + fieldValue(payload, "preferred_regions"),
        "核心诉求：" + fieldValue(payload, "career_goal"),
        "家庭资源：" + fieldValue(payload, "family_background"),
        "是否接受考研：" + (payload.accept_postgraduate === "y" ? "可以接受" : "不优先"),
        "",
        "确认后才会开始查询。"
      ].join("\\n");
    }

    function requireFields(payload, fields) {
      const missing = fields.filter((key) => !(payload[key] || "").trim());
      if (missing.length) {
        status.textContent = "请先补充：" + missing.join("、");
        return false;
      }
      return true;
    }

    function confirmPayload(payload, fields) {
      if (!requireFields(payload, fields)) {
        return false;
      }
      return window.confirm(describePayload(payload));
    }

    function renderDiagnostics(data) {
      if (!data || !data.candidate_pool || !data.results) {
        diagnostics.style.display = "none";
        diagnostics.innerHTML = "";
        return;
      }
      const pool = data.candidate_pool;
      const results = data.results;
      const inventory = data.source_inventory || {};
      const messages = data.messages || [];
      const statusText = inventory.source_status ? inventory.source_status : "未读取到来源审计";
      const nextText = inventory.next_action ? inventory.next_action : "暂无下一步动作";
      diagnostics.style.display = "block";
      diagnostics.innerHTML = `
        <h3>数据诊断</h3>
        <div class="diagnostics-grid">
          <div class="diag-item"><span class="diag-label">原始候选</span><span class="diag-value">${pool.raw_records}</span></div>
          <div class="diag-item"><span class="diag-label">过滤后候选</span><span class="diag-value">${pool.after_filters}</span></div>
          <div class="diag-item"><span class="diag-label">展示结果</span><span class="diag-value">${results.total}</span></div>
          <div class="diag-item"><span class="diag-label">低置信结果</span><span class="diag-value">${results.low_confidence_results}</span></div>
          <div class="diag-item"><span class="diag-label">无可靠位次</span><span class="diag-value">${results.missing_rank_results}</span></div>
          <div class="diag-item"><span class="diag-label">外省参考</span><span class="diag-value">${results.external_reference_results}</span></div>
        </div>
        <ul class="diag-messages">
          <li>来源状态：${statusText}</li>
          <li>下一步：${nextText}</li>
          ${messages.map((message) => `<li>${message}</li>`).join("")}
        </ul>
      `;
    }

    matchRank.addEventListener("click", async () => {
      const payload = currentPayload();
      if (!confirmPayload(payload, ["province", "subject_type", "score"])) {
        return;
      }

      const province = payload.province.trim();
      const subjectType = payload.subject_type.trim();
      const score = payload.score.trim();

      if (!province || !subjectType || !score) {
        status.textContent = "请先填写省份、科类和分数";
        return;
      }

      status.textContent = "正在匹配位次...";

      try {
        const response = await fetch("/rank", {
          method: "POST",
          headers: {
            "Content-Type": "application/json; charset=utf-8"
          },
          body: JSON.stringify({
            province,
            subject_type: subjectType,
            score
          })
        });

        if (!response.ok) {
          throw new Error("接口返回异常: " + response.status);
        }

        const data = await response.json();
        if (!data.rank) {
          status.textContent = "暂无该省份/科类位次表";
          return;
        }

        form.elements.namedItem("rank").value = data.rank;
        status.textContent = "已匹配位次 " + data.rank;
      } catch (error) {
        status.textContent = "位次匹配失败";
      }
    });

    runResearch.addEventListener("click", async () => {
      const payload = currentPayload();
      if (!confirmPayload(payload, ["province", "subject_type"])) {
        return;
      }

      status.textContent = "正在联网取证...";
      researchSummary.style.display = "block";
      researchSummary.textContent = "正在搜索公开来源并抽取数字线索，请稍等。";
      evidenceCards.innerHTML = "";

      try {
        const response = await fetch("/research", {
          method: "POST",
          headers: {
            "Content-Type": "application/json; charset=utf-8"
          },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          throw new Error("接口返回异常: " + response.status);
        }

        const data = await response.json();
        researchSummary.textContent = data.summary;
        status.textContent = "已取证 " + data.evidence.length + " 条来源";

        data.evidence.forEach((item) => {
          const card = document.createElement("article");
          card.className = "card";
          const clues = item.numeric_clues.length ? item.numeric_clues.join("；") : "暂未抽到明确数字线索";
          const link = item.url ? `<p><a href="${item.url}" target="_blank" rel="noreferrer">打开来源</a></p>` : "";
          card.innerHTML = `
            <div class="tier">${item.source_type}</div>
            <h3>${item.title}</h3>
            <div class="meta">${item.purpose} · ${item.status}</div>
            <p><strong>查询：</strong>${item.query}</p>
            <p><strong>摘要：</strong>${item.snippet}</p>
            <p><strong>数字线索：</strong>${clues}</p>
            ${link}
          `;
          evidenceCards.appendChild(card);
        });
      } catch (error) {
        researchSummary.textContent = "联网取证失败：" + error.message;
        status.textContent = "取证失败";
      }
    });

    exportReport.addEventListener("click", async () => {
      const payload = currentPayload();
      if (!confirmPayload(payload, ["province", "subject_type"])) {
        return;
      }
      if (!(payload.score || "").trim() && !(payload.rank || "").trim()) {
        status.textContent = "请至少填写分数或位次";
        return;
      }

      status.textContent = "正在导出报告...";
      summary.textContent = "正在整理正式 HTML 报告，请稍等。";

      try {
        const response = await fetch("/export-report", {
          method: "POST",
          headers: {
            "Content-Type": "application/json; charset=utf-8"
          },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          throw new Error("接口返回异常: " + response.status);
        }

        const data = await response.json();
        const pathText = data.path || "报告路径待返回";
        const linkText = data.fileUrl
          ? '<br><br><a href="' + data.fileUrl + '" target="_blank" rel="noreferrer">点击打开报告</a>'
          : "";
        summary.innerHTML = "报告已导出：<br>" + pathText + linkText;
        status.textContent = "报告已导出";
      } catch (error) {
        summary.textContent = "导出失败：" + error.message;
        status.textContent = "导出失败";
      }
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = currentPayload();
      if (!confirmPayload(payload, ["province", "subject_type"])) {
        return;
      }
      if (!(payload.score || "").trim() && !(payload.rank || "").trim()) {
        status.textContent = "请至少填写分数或位次";
        return;
      }

      status.textContent = "正在计算...";
      cards.innerHTML = "";
      evidenceCards.innerHTML = "";
      researchSummary.style.display = "none";
      diagnostics.style.display = "none";
      diagnostics.innerHTML = "";
      empty.style.display = "none";
      summary.textContent = "正在生成推荐，请稍等。";

      try {
        const response = await fetch("/recommend", {
          method: "POST",
          headers: {
            "Content-Type": "application/json; charset=utf-8"
          },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          throw new Error("接口返回异常: " + response.status);
        }

        const data = await response.json();
        summary.textContent = data.summary;
        status.textContent = "已生成 " + data.recommendations.length + " 条结果";
        renderDiagnostics(data.diagnostics);

        if (!data.recommendations.length) {
          empty.style.display = "block";
          empty.textContent = "当前没有匹配结果。可以放宽城市偏好，或者补充更多数据。";
          return;
        }

        data.recommendations.forEach((item) => {
          const card = document.createElement("article");
          card.className = "card";
          const rankText = item.min_rank ? "最低位次 " + item.min_rank : "位次未可靠入库";
          card.innerHTML = `
            <div class="tier tier-${item.tier}">${item.tier}档</div>
            <h3>${item.school_name}</h3>
            <div class="meta">${item.major_name} · ${item.city} · ${item.year}年 · ${rankText}</div>
            <p><strong>理由：</strong>${item.reason}</p>
            <p><strong>风险：</strong>${item.risk}</p>
            <p><strong>匹配分：</strong>${item.fit_score}</p>
            <p><strong>评分依据：</strong>${(item.score_breakdown || []).join("；")}</p>
          `;
          cards.appendChild(card);
        });
      } catch (error) {
        summary.textContent = "加载失败：" + error.message;
        status.textContent = "请求失败";
        empty.style.display = "block";
        empty.textContent = "接口请求失败，请确认本地服务是否仍在运行。";
      }
    });
  </script>
</body>
</html>
"""
