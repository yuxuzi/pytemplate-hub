// Spotlight: four slides, each shown for 8 seconds (the tab's bar fills). It pauses on hover or
// focus, and on the pause button. With prefers-reduced-motion it starts paused and does not move.
const SLIDE_MS = 8000;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

export function initSpotlight(root) {
  const slides = Array.from(root.querySelectorAll("[data-slide]"));
  const tabs = Array.from(root.querySelectorAll("[data-tab]"));
  const pause = root.querySelector("#spot-pause");
  if (slides.length === 0 || tabs.length !== slides.length || !pause) return;

  let current = 0;
  let userPaused = false;

  function show(index, focus = false) {
    current = (index + slides.length) % slides.length;
    slides.forEach((slide, i) => {
      slide.hidden = i !== current;
      slide.classList.toggle("enter", i === current);
    });
    tabs.forEach((tab, i) => {
      tab.setAttribute("aria-selected", String(i === current));
      tab.tabIndex = i === current ? 0 : -1;
      restartBar(tab.querySelector(".bar"));
    });
    if (focus) tabs[current].focus();
  }

  // Restarting the bar's CSS animation is what advances the slide: animationend moves on.
  function restartBar(bar) {
    if (!bar) return;
    bar.style.animation = "none";
    void bar.offsetWidth;
    bar.style.animation = "";
  }

  function setPaused(paused) {
    userPaused = paused;
    root.classList.toggle("paused", paused);
    pause.setAttribute("aria-pressed", String(paused));
    pause.setAttribute("aria-label", paused ? "Play the spotlight" : "Pause the spotlight");
    pause.querySelector(".icon-pause").hidden = paused;
    pause.querySelector(".icon-play").hidden = !paused;
  }

  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => show(i));
    tab.addEventListener("keydown", (event) => {
      if (event.key === "ArrowRight") show(current + 1, true);
      if (event.key === "ArrowLeft") show(current - 1, true);
    });
    const bar = tab.querySelector(".bar");
    if (bar) {
      bar.addEventListener("animationend", () => {
        if (!userPaused && !root.classList.contains("hold")) show(current + 1);
      });
    }
  });

  pause.addEventListener("click", () => setPaused(!userPaused));
  root.addEventListener("mouseenter", () => root.classList.add("hold"));
  root.addEventListener("mouseleave", () => root.classList.remove("hold"));
  root.addEventListener("focusin", () => root.classList.add("hold"));
  root.addEventListener("focusout", () => root.classList.remove("hold"));

  if (reduceMotion.matches) {
    root.classList.add("static");
    setPaused(true);
  }
  show(0);
}

const spot = document.getElementById("spot");
if (spot) initSpotlight(spot);
