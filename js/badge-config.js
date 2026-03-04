// ── Badge Config ──────────────────────────────────────────
// Set earned: true to unlock a badge, false to keep it locked
// ──────────────────────────────────────────────────────────
const BADGES = [
  { id: 1, earned: true },  // Spark   — Publish your 1st article
  { id: 2, earned: false },  // Quill   — Publish 5 articles
  { id: 3, earned: false },  // Tide    — Write a 3000+ word deep dive
  { id: 4, earned: false },  // Forge   — Document a full project end-to-end
  { id: 5, earned: false },  // Streak  — Post consistently for 6 months
  { id: 6, earned: false },  // Lore    — Reach 25 published articles
  { id: 7, earned: false },  // Signal  — Get featured or cited externally
  { id: 8, earned: false },  // Legend  — 100 articles. You are the champion.
];

document.addEventListener("DOMContentLoaded", function () {
  BADGES.forEach(({ id, earned }) => {
    document.querySelectorAll(`.badge-${id}`).forEach(el => {
      el.style.backgroundImage = `url('/imgs/badge_${id}.png')`;
      el.style.backgroundSize = "cover";
      el.style.backgroundPosition = "center";
      if (!earned) {
        el.style.filter = "grayscale(1) opacity(0.35)";
      } else {
        el.style.filter = "none";
      }
      // clear inner svg since we're using image now
      const svg = el.querySelector("svg");
      if (svg) svg.style.display = "none";
    });
  });
});
