// Render <time class="local-time" datetime="...Z"> in the viewer's timezone.
(function () {
  const fmt = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  function localize(root) {
    (root || document).querySelectorAll("time.local-time[datetime]").forEach((el) => {
      const d = new Date(el.getAttribute("datetime"));
      if (isNaN(d)) return;
      el.textContent = fmt.format(d);
      el.title = d.toISOString();
    });
  }

  document.addEventListener("DOMContentLoaded", () => localize());
  document.addEventListener("htmx:afterSettle", () => localize());
  if (document.readyState !== "loading") localize();
})();
