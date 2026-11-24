// Segmented controls: one radio group each.
function seg(el, on) {
  const bs = [...el.querySelectorAll("button")];
  bs.forEach((b) => b.addEventListener("click", () => {
    bs.forEach((x) => x.setAttribute("aria-checked", String(x === b)));
    on(b.dataset.v);
  }));
  return bs;
}
// The matrix shows one agent at a time.
const mxSeg = document.getElementById("mx-seg");
if (mxSeg) seg(mxSeg, (v) => document.querySelectorAll(".mx-pane").forEach((p) => (p.hidden = p.dataset.agent !== v)));
// Filter the calls by group, or to the ones that missed.
const callSeg = seg(document.getElementById("call-seg"), (v) => {
  document.querySelectorAll(".call").forEach((c) => {
    c.hidden = !(v === "all" || (v === "missed" ? c.dataset.missed === "1" : c.dataset.group === v));
  });
});
// Any link to a call opens it and shows it, whatever the filter.
function openCall(id) {
  const d = document.getElementById("call-" + id);
  if (!d) return;
  callSeg[0].click();
  d.open = true;
  document.querySelectorAll(".call.lit").forEach((x) => x.classList.remove("lit"));
  d.classList.add("lit");
  d.scrollIntoView({ behavior: "smooth", block: "start" });
}
document.addEventListener("click", (e) => {
  const a = e.target.closest('a[href^="#call-"]');
  if (!a) return;
  e.preventDefault();
  const id = a.getAttribute("href").slice(6);
  history.replaceState(null, "", "#call-" + id);
  openCall(id);
});
if (location.hash.startsWith("#call-")) openCall(location.hash.slice(6));
// A square lifts its twins in the other rows.
document.addEventListener("mouseover", (e) => {
  const c = e.target.closest(".cell[data-case]");
  document.querySelectorAll(".cell.lit").forEach((x) => x.classList.remove("lit"));
  if (c) document.querySelectorAll(`.cell[data-case="${c.dataset.case}"]`).forEach((x) => x.classList.add("lit"));
});
// Expand or collapse every call at once.
const all = document.getElementById("open-all");
if (all) all.addEventListener("click", () => {
  const open = all.getAttribute("aria-expanded") !== "true";
  all.setAttribute("aria-expanded", String(open));
  all.textContent = open ? "Collapse all" : "Expand all";
  document.querySelectorAll(".call:not([hidden])").forEach((d) => (d.open = open));
});
// Highlight the section in view in the side navigation.
const links = [...document.querySelectorAll(".side nav a")];
const secs = links.map((a) => document.querySelector(a.getAttribute("href"))).filter(Boolean);
if ("IntersectionObserver" in window) {
  const seen = new Map();
  const io = new IntersectionObserver((es) => {
    es.forEach((x) => seen.set(x.target, x.isIntersecting));
    const cur = secs.find((s) => seen.get(s));
    if (cur) links.forEach((a) => a.classList.toggle("on", a.getAttribute("href") === "#" + cur.id));
  }, { rootMargin: "-10% 0px -60% 0px" });
  secs.forEach((s) => io.observe(s));
}
