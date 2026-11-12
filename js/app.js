// Theme toggle, example browsers and citation tabs.
(function () {
  "use strict";

  // Theme: the initial value is set in <head>; the toggle switches and remembers it.
  var root = document.documentElement;
  var toggle = document.getElementById("theme-toggle");
  function label() {
    var dark = root.getAttribute("data-theme") === "dark";
    toggle.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    toggle.title = toggle.getAttribute("aria-label");
  }
  toggle.addEventListener("click", function () {
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
    label();
  });
  // Follow system changes until the visitor picks a theme.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
    var saved = null;
    try { saved = localStorage.getItem("theme"); } catch (err) {}
    if (!saved) {
      root.setAttribute("data-theme", e.matches ? "dark" : "light");
      label();
    }
  });
  label();

  function highlight(el, code) {
    el.textContent = code;
    el.removeAttribute("data-highlighted");
    if (window.hljs) window.hljs.highlightElement(el);
  }

  function fill(select, items) {
    items.forEach(function (item, i) {
      var option = document.createElement("option");
      option.value = i;
      option.textContent = (i + 1) + ") " + item.title;
      select.appendChild(option);
    });
  }

  // Policies: code, plus a video when one exists for the task.
  var policies = window.AP_POLICIES || [];
  var policySelect = document.getElementById("policy-select");
  var policyCode = document.getElementById("policy-code");
  var policyVideo = document.getElementById("policy-video");
  function showPolicy(i) {
    var p = policies[i];
    highlight(policyCode, p.code);
    policyVideo.innerHTML = "";
    policyVideo.hidden = !p.video;
    if (p.video) {
      var video = document.createElement("video");
      video.src = p.video;
      video.controls = true;
      video.preload = "metadata";
      video.playsInline = true;
      policyVideo.appendChild(video);
    }
  }
  fill(policySelect, policies);
  policySelect.addEventListener("change", function () { showPolicy(+policySelect.value); });
  if (policies.length) showPolicy(0);

  // Recoveries: the failure context and the code the model writes.
  var recoveries = window.AP_RECOVERIES || [];
  var recoverySelect = document.getElementById("recovery-select");
  var triggers = { action: "A failed action", checkpoint: "A failed checkpoint", exception: "An exception in generated code" };
  function showRecovery(i) {
    var r = recoveries[i];
    document.getElementById("recovery-trigger").textContent = triggers[r.trigger] || r.trigger;
    document.getElementById("recovery-failure").textContent = r.failure;
    document.getElementById("recovery-observation").textContent = r.observation || "not shown";
    highlight(document.getElementById("recovery-code"), r.code);
  }
  fill(recoverySelect, recoveries);
  recoverySelect.addEventListener("change", function () { showRecovery(+recoverySelect.value); });
  if (recoveries.length) showRecovery(0);

  // Highlight the static code blocks.
  document.querySelectorAll("section.narrow pre code.language-python").forEach(function (el) {
    if (window.hljs) window.hljs.highlightElement(el);
  });

  // Citation tabs (arrow keys move between tabs) and copy buttons.
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.cite [role="tab"]'));
  function select(tab) {
    tabs.forEach(function (t) {
      var on = t === tab;
      t.setAttribute("aria-selected", on);
      t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    });
  }
  tabs.forEach(function (tab, i) {
    tab.addEventListener("click", function () { select(tab); });
    tab.addEventListener("keydown", function (e) {
      var step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (step) {
        var next = tabs[(i + step + tabs.length) % tabs.length];
        select(next);
        next.focus();
      }
    });
  });
  document.querySelectorAll(".copy").forEach(function (button) {
    button.addEventListener("click", function () {
      var text = button.parentElement.querySelector("code").textContent;
      navigator.clipboard.writeText(text).then(function () {
        button.textContent = "Copied";
        setTimeout(function () { button.textContent = "Copy"; }, 1500);
      });
    });
  });
})();
