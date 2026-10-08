/**
 * TeachClone Embeddable Widget — floating chat button for external websites.
 *
 * Usage:
 *   <script
 *     src="https://app.teachclone.com/teachclone-widget.js"
 *     data-teacher-id="prof-sharma-physics"
 *     data-grade="class-11-12"
 *     data-theme="light">
 *   </script>
 */
(function () {
  "use strict";

  const script = document.currentScript;
  const teacherId = script.getAttribute("data-teacher-id");
  const grade = script.getAttribute("data-grade") || "class-9-10";
  const theme = script.getAttribute("data-theme") || "light";
  const baseUrl = script.getAttribute("data-base-url") || "https://app.teachclone.com";

  if (!teacherId) {
    console.error("[TeachClone] data-teacher-id attribute is required.");
    return;
  }

  // --- Container (iframe wrapper) ---
  const container = document.createElement("div");
  container.id = "teachclone-widget-container";
  container.style.cssText = [
    "position: fixed; bottom: 24px; right: 24px;",
    "width: 380px; height: 600px; z-index: 9999;",
    "border-radius: 12px; overflow: hidden;",
    "box-shadow: 0 8px 32px rgba(0,0,0,0.18);",
    "display: none; flex-direction: column;",
    "transition: opacity 0.2s;",
  ].join(" ");

  // --- Iframe ---
  const iframe = document.createElement("iframe");
  const src = `${baseUrl}/embed/${teacherId}?grade=${encodeURIComponent(grade)}&theme=${encodeURIComponent(theme)}`;
  iframe.src = src;
  iframe.style.cssText = "width:100%; height:100%; border:none;";
  iframe.allow = "microphone";
  iframe.title = "TeachClone Chat";

  // --- Toggle button ---
  const btn = document.createElement("button");
  btn.innerHTML = "\uD83D\uDCAC Ask Teacher";
  btn.style.cssText = [
    "position: fixed; bottom: 24px; right: 24px; z-index: 9998;",
    "background: #1D9E75; color: #fff; border: none; border-radius: 999px;",
    "padding: 12px 20px; font-size: 15px; font-family: inherit;",
    "cursor: pointer; box-shadow: 0 4px 16px rgba(0,0,0,0.15);",
    "transition: transform 0.15s;",
  ].join(" ");
  btn.addEventListener("mouseenter", () => { btn.style.transform = "scale(1.05)"; });
  btn.addEventListener("mouseleave", () => { btn.style.transform = "scale(1)"; });

  let open = false;

  btn.addEventListener("click", () => {
    open = !open;
    container.style.display = open ? "flex" : "none";
    btn.innerHTML = open ? "\u2715 Close" : "\uD83D\uDCAC Ask Teacher";
  });

  // --- Listen for messages from iframe ---
  window.addEventListener("message", (event) => {
    if (event.origin !== baseUrl) return;
    if (event.data?.type === "teachclone:resize") {
      container.style.height = event.data.height + "px";
    }
    if (event.data?.type === "teachclone:close") {
      open = false;
      container.style.display = "none";
      btn.innerHTML = "\uD83D\uDCAC Ask Teacher";
    }
  });

  container.appendChild(iframe);
  document.body.appendChild(container);
  document.body.appendChild(btn);
})();
