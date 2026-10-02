/* PocketSmart AI - frontend logic (vanilla JS, no build step) */
(() => {
  "use strict";

  // ------------------------------------------------------------------ helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const inr = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
  const esc = (v) =>
    String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pretty = (s) => String(s || "").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
  const when = (iso) =>
    new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });

  const SITE = {
    amazon: "Amazon", flipkart: "Flipkart", ikea: "IKEA", pepperfry: "Pepperfry", myntra: "Myntra",
    meesho: "Meesho", bigbasket: "BigBasket", swiggy: "Swiggy", zomato: "Zomato", bookmyshow: "BookMyShow",
    google: "Google", maps: "Google Maps", booking: "Booking.com", makemytrip: "MakeMyTrip", oyo: "OYO",
    nobroker: "NoBroker", bluestone: "BlueStone", tanishq: "Tanishq", caratlane: "CaratLane", melorra: "Melorra",
  };
  const KIND = {
    home: { icon: "🏠", title: "Home interior plan" },
    party: { icon: "🎉", title: "Party plan" },
    jewelry: { icon: "💎", title: "Jewelry plan" },
  };

  const chips = (links) =>
    Object.entries(links || {})
      .filter(([, url]) => /^https:\/\//.test(url))
      .map(([site, url]) =>
        `<a class="chip" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(SITE[site] || pretty(site))}</a>`)
      .join("");

  function errorText(data) {
    const d = data && data.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d))
      return d.map((e) => {
        const field = (e.loc || []).slice(1).join(" ");
        return (field ? field + ": " : "") + String(e.msg).replace("Value error, ", "");
      }).join("; ");
    return "";
  }

  async function api(url, options = {}) {
    const res = await fetch(url, { credentials: "same-origin", ...options });
    let data = null;
    try { data = await res.json(); } catch (_) { /* non-JSON response */ }
    if (res.status === 401 && url !== "/token") {
      window.location.href = "/login";
      throw new Error("Your session expired. Please sign in again.");
    }
    if (!res.ok) throw new Error(errorText(data) || `Request failed (${res.status})`);
    return data;
  }

  function message(el, text, type = "error") {
    if (!el) return;
    el.className = `alert ${type}`;
    el.textContent = text;
    el.hidden = !text;
  }

  // ------------------------------------------------------------------ result rendering
  const badge = (d) =>
    d.source === "gemini"
      ? '<span class="badge ok">Gemini AI</span>'
      : '<span class="badge warn">Demo mode</span>';

  const notice = (d) => (d.notice ? `<div class="alert warn">${esc(d.notice)}</div>` : "");

  function summary(d) {
    const pct = d.total_budget ? Math.max(0, Math.min(100, (d.allocated / d.total_budget) * 100)) : 0;
    return `${notice(d)}
    <section class="panel">
      <header class="panel-h"><h2>Budget summary</h2>${badge(d)}</header>
      <div class="stats">
        <div><span>Total budget</span><strong>${inr(d.total_budget)}</strong></div>
        <div><span>Planned spend</span><strong>${inr(d.allocated)}</strong></div>
        <div><span>Remaining</span><strong class="pos">${inr(d.remaining_budget)}</strong></div>
      </div>
      <div class="bar" role="img" aria-label="${pct.toFixed(0)} percent of the budget planned"><i style="width:${pct.toFixed(1)}%"></i></div>
    </section>`;
  }

  function categoryPanel(cat) {
    const rows = cat.items.map((i) => `
      <tr>
        <td><strong>${esc(i.name)}</strong><small>${esc(i.description)}</small></td>
        <td class="num">${inr(i.estimated_price)}</td>
        <td class="num">${esc(i.quantity)}</td>
        <td class="num">${inr(i.line_total)}</td>
        <td class="links">${chips(i.shopping_links)}</td>
      </tr>`).join("");
    return `<section class="panel">
      <header class="panel-h"><h3>${esc(pretty(cat.category))}</h3><strong>${inr(cat.allocation)}</strong></header>
      <div class="table-wrap"><table>
        <thead><tr><th>Item</th><th class="num">Unit price</th><th class="num">Qty</th><th class="num">Total</th><th>Find it on</th></tr></thead>
        <tbody>${rows}</tbody></table></div></section>`;
  }

  const calcTable = (d) => `<section class="panel">
    <header class="panel-h"><h3>Cost breakdown</h3></header>
    <div class="table-wrap"><table>
      <thead><tr><th>Category</th><th class="num">Items</th><th class="num">Cost</th><th class="num">Share of budget</th></tr></thead>
      <tbody>${d.calculation_table.map((r) => `<tr><td>${esc(pretty(r.category))}</td><td class="num">${esc(r.items_count)}</td>
        <td class="num">${inr(r.total_cost)}</td><td class="num">${esc(r.percentage_of_budget)}%</td></tr>`).join("")}</tbody>
    </table></div></section>`;

  const tips = (title, list) =>
    list && list.length
      ? `<section class="panel"><header class="panel-h"><h3>${esc(title)}</h3></header>
         <ul class="list">${list.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></section>`
      : "";

  function venues(d) {
    if (!d.venue_suggestions || !d.venue_suggestions.length) return "";
    const rows = d.venue_suggestions.map((v) => `<tr>
      <td><strong>${esc(v.name)}</strong><small>${esc(v.type)}${v.capacity ? `, up to ${esc(v.capacity)} guests` : ""}</small></td>
      <td class="num">${inr(v.estimated_cost)}</td><td class="links">${chips(v.search_links)}</td></tr>`).join("");
    return `<section class="panel"><header class="panel-h"><h3>Venue ideas</h3></header>
      <div class="table-wrap"><table><thead><tr><th>Venue</th><th class="num">Estimated cost</th><th>Search on</th></tr></thead>
      <tbody>${rows}</tbody></table></div></section>`;
  }

  function renderPlan(d) {
    const printBtn = d.kind === "party" ? '<p class="no-print"><button type="button" class="btn light small" data-print>Print or save as PDF</button></p>' : "";
    return `${summary(d)}${d.budget_breakdown.map(categoryPanel).join("")}${venues(d)}${calcTable(d)}
      ${tips("Money-saving tips", d.additional_suggestions)}${printBtn}`;
  }

  function renderJewelry(d) {
    const o = d.outfit_analysis;
    const outfit = o ? `<section class="panel"><header class="panel-h"><h3>Outfit analysis</h3></header>
      <div class="tagline">
        <span class="tag">Colors: ${esc((o.colors || []).join(", ") || "n/a")}</span>
        <span class="tag">Style: ${esc(o.style || "n/a")}</span>
        <span class="tag">Formality: ${esc(o.formality || "n/a")}</span></div></section>` : "";
    const cards = d.jewelry_recommendations.map((r) => `<section class="panel">
      <header class="panel-h"><h3>${esc(pretty(r.item_type))}</h3><strong>${inr(r.estimated_price)}</strong></header>
      <div class="panel-body"><p>${esc(r.description)}</p>
        ${r.style ? `<p class="hint">Style: ${esc(r.style)}</p>` : ""}
        <div>${chips(r.shopping_links)}</div></div></section>`).join("");
    return `${summary(d)}${outfit}${cards}${tips("Styling tips", d.styling_tips)}`;
  }

  const renderResult = (d) => (d.kind === "jewelry" ? renderJewelry(d) : renderPlan(d));

  // ------------------------------------------------------------------ planner forms
  const val = (f, n) => f.elements[n];
  const num = (f, n) => parseFloat(val(f, n).value);
  const toInt = (f, n) => parseInt(val(f, n).value || "0", 10);
  const chk = (f, n) => val(f, n).checked;
  const txt = (f, n) => (val(f, n).value || "").trim() || null;

  const PLANNERS = {
    home: {
      url: "/home-budget",
      body: (f) => ({
        total_budget: num(f, "total_budget"), num_lights: toInt(f, "num_lights"), num_fans: toInt(f, "num_fans"),
        num_furniture: toInt(f, "num_furniture"), num_dining_tables: toInt(f, "num_dining_tables"),
        has_living_room: chk(f, "has_living_room"), has_kitchen: chk(f, "has_kitchen"), has_bedroom: chk(f, "has_bedroom"),
        additional_requirements: txt(f, "additional_requirements"),
      }),
    },
    party: {
      url: "/party-budget",
      body: (f) => ({
        total_budget: num(f, "total_budget"), num_guests: toInt(f, "num_guests"), party_type: val(f, "party_type").value,
        venue_type: val(f, "venue_type").value, needs_catering: chk(f, "needs_catering"),
        needs_decoration: chk(f, "needs_decoration"), needs_entertainment: chk(f, "needs_entertainment"),
        additional_requirements: txt(f, "additional_requirements"),
      }),
    },
    jewelry: {
      url: "/jewelry-budget",
      body: (f) => {
        const fd = new FormData(f);
        const file = val(f, "image").files[0];
        if (!file) fd.delete("image");
        return fd;
      },
    },
  };

  function initPlanner(form) {
    const cfg = PLANNERS[form.dataset.planner];
    const out = $("#results");
    const msg = $("#form-msg");
    const btn = $("button[type=submit]", form);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      message(msg, "");
      const label = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Building your plan...";
      out.innerHTML = '<div class="loading" role="status"><span class="spinner"></span> Working out the best split for your budget. This can take up to a minute.</div>';
      try {
        const body = cfg.body(form);
        const options = body instanceof FormData
          ? { method: "POST", body }
          : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
        const data = await api(cfg.url, options);
        out.innerHTML = renderResult(data);
        out.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (err) {
        out.innerHTML = "";
        message(msg, err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = label;
      }
    });

    const file = form.elements.image;      // jewelry planner only
    if (file) {
      const preview = $("#preview");
      const remove = $("#remove-image");
      file.addEventListener("change", () => {
        const f = file.files[0];
        if (!f) { preview.hidden = remove.hidden = true; return; }
        if (f.size > 5 * 1024 * 1024 || !/^image\/(jpeg|png|webp)$/.test(f.type)) {
          file.value = "";
          preview.hidden = remove.hidden = true;
          message(msg, "Choose a JPG, PNG or WebP image under 5 MB.");
          return;
        }
        message(msg, "");
        preview.src = URL.createObjectURL(f);
        preview.hidden = remove.hidden = false;
      });
      remove.addEventListener("click", () => { file.value = ""; preview.hidden = remove.hidden = true; });
    }
  }

  document.addEventListener("click", (e) => { if (e.target.closest("[data-print]")) window.print(); });

  // ------------------------------------------------------------------ auth forms
  const login = (username, password) =>
    api("/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username, password }),
    });

  function initLogin(form) {
    const msg = $("#form-msg");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      message(msg, "");
      try {
        await login(val(form, "username").value, val(form, "password").value);
        window.location.href = "/dashboard";
      } catch (err) { message(msg, err.message); }
    });
  }

  function initRegister(form) {
    const msg = $("#form-msg");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      message(msg, "");
      const password = val(form, "password").value;
      if (password !== val(form, "confirm").value) return message(msg, "Passwords do not match.");
      const username = val(form, "username").value.trim();
      try {
        await api("/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, email: val(form, "email").value.trim(), full_name: txt(form, "full_name"), password }),
        });
        await login(username, password);
        window.location.href = "/dashboard";
      } catch (err) { message(msg, err.message); }
    });
  }

  // ------------------------------------------------------------------ history + dashboard
  function historyCard(h) {
    const k = KIND[h.type] || KIND.home;
    const i = h.input_data || {};
    let facts = "";
    if (h.type === "home") {
      const rooms = [i.has_living_room && "Living room", i.has_kitchen && "Kitchen", i.has_bedroom && "Bedroom"].filter(Boolean).join(", ");
      facts = `Rooms: ${rooms || "none"}. Lights ${i.num_lights}, fans ${i.num_fans}, furniture ${i.num_furniture}, dining tables ${i.num_dining_tables}.`;
    } else if (h.type === "party") {
      const needs = [i.needs_catering && "Catering", i.needs_decoration && "Decoration", i.needs_entertainment && "Entertainment"].filter(Boolean).join(", ");
      facts = `${pretty(i.party_type)} for ${i.num_guests} guests. Needs: ${needs}.`;
    } else {
      facts = `Occasion: ${i.occasion}. Outfit image: ${i.has_image ? "yes" : "no"}.`;
    }
    return `<article class="hcard ${esc(h.type)}">
      <header><h3>${k.icon} ${esc(k.title)}</h3><small>${esc(when(h.timestamp))}</small></header>
      <dl><div><dt>Total budget</dt><dd>${inr(h.total_budget)}</dd></div><div><dt>Remaining</dt><dd>${inr(h.remaining_budget)}</dd></div></dl>
      <p>${esc(facts)}</p>
      <button class="btn small" type="button" data-id="${esc(h.id)}">View full details</button></article>`;
  }

  async function initHistory(box) {
    const dlg = $("#detail-dialog");
    const body = $("#detail-body");
    try {
      const { history } = await api("/recommendation-history?limit=100");
      box.innerHTML = history.length
        ? history.map(historyCard).join("")
        : '<div class="empty">No plans yet. Create one from the Home, Party or Jewelry planner.</div>';
    } catch (err) { box.innerHTML = `<div class="alert error">${esc(err.message)}</div>`; }

    box.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-id]");
      if (!btn) return;
      body.innerHTML = '<div class="loading"><span class="spinner"></span> Loading...</div>';
      dlg.showModal();
      try {
        const d = await api(`/recommendation-details/${encodeURIComponent(btn.dataset.id)}`);
        body.innerHTML = renderResult(d.full_result);
      } catch (err) { body.innerHTML = `<div class="alert error">${esc(err.message)}</div>`; }
    });
    $("#close-dialog").addEventListener("click", () => dlg.close());
  }

  async function initRecent(list) {
    try {
      const { history } = await api("/recommendation-history?limit=5");
      list.innerHTML = history.length
        ? history.map((h) => {
            const k = KIND[h.type] || KIND.home;
            return `<li><span class="ico">${k.icon}</span><div><strong>${esc(k.title)}</strong>
              <small>${esc(h.input)}</small><small>${esc(when(h.timestamp))}</small></div></li>`;
          }).join("")
        : '<li class="empty">Nothing here yet. Pick a planner above to create your first plan.</li>';
    } catch (err) { list.innerHTML = `<li class="empty">${esc(err.message)}</li>`; }
  }

  // ------------------------------------------------------------------ boot
  document.addEventListener("DOMContentLoaded", () => {
    const planner = $("form[data-planner]");
    if (planner) initPlanner(planner);
    if ($("#login-form")) initLogin($("#login-form"));
    if ($("#register-form")) initRegister($("#register-form"));
    if ($("#history-list")) initHistory($("#history-list"));
    if ($("#recent-list")) initRecent($("#recent-list"));
  });
})();
