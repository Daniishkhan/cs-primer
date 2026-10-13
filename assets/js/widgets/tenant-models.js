/* Tenancy model explorer (security chapter 15).
   Compares silo (a full stack per tenant), bridge (shared application tier, a database per tenant) and
   pool (everything shared, rows tagged by tenant) for N tenants. Pick a model and an incident; the widget
   shows how many OTHER tenants are affected, plus relative cost per tenant and the number of things to operate.
   The cost and operations figures are teaching assumptions (a stack costs 10 units, a shared app tier 2, a database 3,
   a pooled row-store marginal 0.5 per tenant), not measurements. "Bridge" is used loosely: real systems mix
   models, for example pool for small tenants and silo for large ones. No storage, no network. */
(function () {
  "use strict";
  var root = document.getElementById("tenant-models");
  if (!root) return;
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  var MODELS = [
    { id: "silo",   name: "Silo",   desc: "Each tenant gets its own full stack: app servers, database, often its own cloud account or cluster." },
    { id: "bridge", name: "Bridge", desc: "A shared application tier, but each tenant has its own database (or schema). One common mix of the two ends." },
    { id: "pool",   name: "Pool",   desc: "Everything is shared. Rows carry a tenant_id and every query, cache key and job must respect it." }
  ];
  var INCIDENTS = [
    { id: "filter", name: "A query forgets its tenant filter" },
    { id: "route",  name: "Tenant context is wrong or forged" },
    { id: "noisy",  name: "One tenant floods the system" },
    { id: "cred",   name: "The app's data credentials leak" },
    { id: "deploy", name: "A bad release ships" }
  ];

  /* returns {n: tenants affected besides the origin, note} */
  function impact(model, inc, N) {
    var others = N - 1;
    var T = {
      silo: {
        filter: [0, "The stack only holds one tenant's data. There is nothing else to leak."],
        route:  [0, "Separate stacks and networks: a wrong tenant id has no other tenant's data to reach."],
        noisy:  [0, "The flood is limited to its own stack. It may cost that tenant, not its neighbours."],
        cred:   [0, "Each stack has its own credential, so one leak exposes one tenant."],
        deploy: [0, "Roll out stack by stack and stop when canaries fail. Slower, but the blast radius is yours to choose."]
      },
      bridge: {
        filter: [0, "Queries run against the tenant's own database, so a missing WHERE cannot cross tenants."],
        route:  [others, "The shared app tier can connect to every database. If it picks the wrong one, any tenant is reachable."],
        noisy:  [others, "The shared app tier saturates for everyone (the databases stay isolated)."],
        cred:   [N, "The shared app tier holds a credential or secret for every tenant database."],
        deploy: [N, "One shared app tier means one release for everyone, unless you canary by cohort."]
      },
      pool: {
        filter: [others, "All tenants' rows sit in the same tables. One missing predicate can expose any of them."],
        route:  [others, "Tenant id is only a column value. A wrong or forged value selects another tenant's rows."],
        noisy:  [others, "CPU, connections and I/O are shared. Without quotas and fair queueing everyone slows down."],
        cred:   [N, "One database credential reaches every tenant's rows."],
        deploy: [N, "One release for all unless you canary by cohort."]
      }
    };
    var r = T[model][inc];
    return { n: r[0], note: r[1] };
  }
  function costPerTenant(model, N) {            /* relative units */
    if (model === "silo") return 10;
    if (model === "bridge") return 2 / N + 3;
    return 10 / N + 0.5;
  }
  function opsTargets(model, N) {
    if (model === "silo") return N + " stacks to deploy, patch, monitor and back up";
    if (model === "bridge") return "1 app tier + " + N + " databases to migrate";
    return "1 stack and 1 database (but one huge migration and one huge blast radius)";
  }

  var st = { model: "pool", inc: "filter", N: 50 };

  var head = h("div", "widget-head");
  head.appendChild(h("span", "widget-tag", "Explore"));
  head.appendChild(h("h4", "widget-title", "Silo, bridge or pool: what does one incident reach?"));
  root.appendChild(head);

  var mrow = h("div", "widget-row tm-row"); mrow.setAttribute("role", "group"); mrow.setAttribute("aria-label", "Tenancy model");
  var mbtns = {};
  MODELS.forEach(function (m) {
    var b = h("button", "btn small", m.name); b.type = "button";
    b.addEventListener("click", function () { st.model = m.id; render(); });
    mbtns[m.id] = b; mrow.appendChild(b);
  });
  root.appendChild(mrow);

  var ctl = h("div", "widget-row tm-row");
  var l1 = h("label", "tm-ctl"); l1.appendChild(h("span", "tm-l", "Incident"));
  var sel = h("select");
  INCIDENTS.forEach(function (i) { var o = h("option", null, i.name); o.value = i.id; sel.appendChild(o); });
  sel.value = st.inc; sel.addEventListener("change", function () { st.inc = sel.value; render(); });
  l1.appendChild(sel); ctl.appendChild(l1);
  var l2 = h("label", "tm-ctl"); var nl = h("span", "tm-l", "Tenants: 50"); l2.appendChild(nl);
  var rng = h("input"); rng.type = "range"; rng.min = "2"; rng.max = "500"; rng.value = "50";
  rng.addEventListener("input", function () { st.N = parseInt(rng.value, 10); render(); });
  l2.appendChild(rng); ctl.appendChild(l2);
  root.appendChild(ctl);

  var desc = h("p", "tm-desc"); root.appendChild(desc);
  var grid = h("div", "tm-grid"); grid.setAttribute("role", "img"); root.appendChild(grid);
  var out = h("div", "widget-out tm-out"); out.setAttribute("aria-live", "polite"); root.appendChild(out);
  var tbl = h("div", "tm-cmp"); root.appendChild(tbl);
  root.appendChild(h("p", "widget-help", "The grid shows up to 40 tenants. The first one (outlined) is where the incident starts; red tenants are also affected. Cost and operations numbers are teaching assumptions, not measurements."));

  function render() {
    var N = st.N, m = MODELS.filter(function (x) { return x.id === st.model; })[0];
    MODELS.forEach(function (x) { mbtns[x.id].className = "btn small" + (x.id === st.model ? " primary" : ""); mbtns[x.id].setAttribute("aria-pressed", x.id === st.model ? "true" : "false"); });
    nl.textContent = "Tenants: " + N;
    desc.textContent = m.desc;
    var im = impact(st.model, st.inc, N);
    var shown = Math.min(N, 40), hitShown = Math.min(shown, im.n >= N - 1 ? shown : Math.round(shown * im.n / Math.max(1, N)));
    grid.textContent = "";
    grid.setAttribute("aria-label", im.n + " other tenants affected out of " + (N - 1));
    for (var i = 0; i < shown; i++) {
      var c = h("span", "tm-cell");
      if (i === 0) c.className += " tm-origin";
      if (i > 0 && i <= hitShown) c.className += " tm-hit";
      grid.appendChild(c);
    }
    out.textContent = "";
    var p = h("p");
    p.appendChild(h("span", "pill " + (im.n === 0 ? "green" : "red"), im.n === 0 ? "CONTAINED" : "SPREADS"));
    var shownN = im.n > N - 1 ? (N - 1) : im.n;
    p.appendChild(document.createTextNode(" " + shownN + " of " + (N - 1) + " other tenants affected. " + im.note));
    out.appendChild(p);

    tbl.textContent = "";
    var t = h("table", "tm-table");
    var hr = h("tr"); ["Model", "Relative cost / tenant", "To operate"].forEach(function (x) { hr.appendChild(h("th", null, x)); }); t.appendChild(hr);
    var base = costPerTenant("silo", N);
    MODELS.forEach(function (x) {
      var tr = h("tr", x.id === st.model ? "tm-sel" : "");
      tr.appendChild(h("td", null, x.name));
      tr.appendChild(h("td", null, Math.round(100 * costPerTenant(x.id, N) / base) + "%"));
      tr.appendChild(h("td", null, opsTargets(x.id, N)));
      t.appendChild(tr);
    });
    tbl.appendChild(t);
  }
  render();
})();
