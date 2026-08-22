(() => {
  const toggle = document.getElementById("tn-nav-toggle");
  const menu = document.getElementById("tn-nav-mobile-menu");
  const iconOpen = document.getElementById("tn-nav-icon-open");
  const iconClose = document.getElementById("tn-nav-icon-close");
  if (!toggle || !menu) return;

  function setOpen(open) {
    menu.classList.toggle("hidden", !open);
    toggle.setAttribute("aria-expanded", String(open));
    if (iconOpen) iconOpen.classList.toggle("hidden", open);
    if (iconClose) iconClose.classList.toggle("hidden", !open);
  }

  toggle.addEventListener("click", () => {
    setOpen(toggle.getAttribute("aria-expanded") !== "true");
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setOpen(false);
  });

  document.addEventListener("click", (event) => {
    if (!menu.contains(event.target) && !toggle.contains(event.target)) {
      setOpen(false);
    }
  });

  // A resize past the desktop nav breakpoint (lg) reveals the inline links;
  // keep the drawer from staying stuck open behind it.
  window.matchMedia("(min-width: 1024px)").addEventListener("change", (event) => {
    if (event.matches) setOpen(false);
  });
})();
