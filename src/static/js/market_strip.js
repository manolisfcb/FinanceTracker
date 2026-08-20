(() => {
  const storageKey = "tn-market-scroll-started-at";

  function readStartTime() {
    try {
      const stored = Number(window.sessionStorage.getItem(storageKey));
      if (Number.isFinite(stored) && stored > 0) return stored;

      const startedAt = Date.now();
      window.sessionStorage.setItem(storageKey, String(startedAt));
      return startedAt;
    } catch (_error) {
      // Some privacy modes disable web storage. The ticker still animates;
      // only cross-page continuity is unavailable in that case.
      return Date.now();
    }
  }

  const startedAt = readStartTime();

  function syncTickerPhase() {
    const track = document.querySelector(".tn-market-track");
    if (!track) return;

    const styles = window.getComputedStyle(track);
    if (styles.animationName === "none") return;

    const durationSeconds = Number.parseFloat(styles.animationDuration);
    if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) return;

    const elapsedSeconds = Math.max(0, (Date.now() - startedAt) / 1000);
    const phaseSeconds = elapsedSeconds % durationSeconds;

    if (typeof track.getAnimations === "function") {
      const scrollingAnimation = track
        .getAnimations()
        .find((animation) => animation.animationName === "tn-market-scroll");
      if (scrollingAnimation) {
        scrollingAnimation.currentTime = phaseSeconds * 1000;
        return;
      }
    }

    // Fallback for older browsers without the Web Animations API.
    track.style.setProperty("--tn-market-animation-delay", `-${phaseSeconds}s`);
  }

  syncTickerPhase();
  window.addEventListener("pageshow", syncTickerPhase);
})();
