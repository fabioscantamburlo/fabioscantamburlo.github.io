document.addEventListener("DOMContentLoaded", function () {
  const flipInner = document.getElementById("tcFlip");
  if (!flipInner) return;

  const front = flipInner.querySelector(".tc-front");
  const wrapper = flipInner.parentElement;

  // Lock wrapper height to front card height so back never changes layout
  const frontHeight = front.offsetHeight;
  wrapper.style.height = frontHeight + "px";
  flipInner.style.height = frontHeight + "px";

  // Make back card fill the same height with legend scrolling inside
  const back = flipInner.querySelector(".tc-back");
  back.style.height = frontHeight + "px";
  const legend = back.querySelector(".tc-badge-legend");
  if (legend) legend.style.maxHeight = (frontHeight - 120) + "px";

  fetch("/imgs/badges.svg")
    .then(r => r.text())
    .then(svg => {
      const div = document.createElement("div");
      div.style.display = "none";
      div.innerHTML = svg;
      document.body.insertBefore(div, document.body.firstChild);
    });
});
