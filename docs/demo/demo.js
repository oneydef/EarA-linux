(function () {
  const toastEl = document.getElementById("toast");
  let toastTimer;

  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.hidden = true;
    }, 2400);
  }

  document.querySelectorAll(".eara-tab[data-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      const name = tab.dataset.tab;
      document.querySelectorAll(".eara-tab[data-tab]").forEach((t) => {
        t.classList.toggle("eara-tab-active", t === tab);
      });
      document.querySelectorAll(".eara-panel-page").forEach((p) => {
        const active = p.dataset.panel === name;
        p.classList.toggle("is-active", active);
        p.hidden = !active;
      });
    });
  });

  document.querySelectorAll(".eara-switch").forEach((sw) => {
    sw.addEventListener("click", () => {
      const on = sw.classList.toggle("is-on");
      sw.setAttribute("aria-pressed", on ? "true" : "false");
      const label = sw.closest(".eara-toggle-row")?.querySelector(".eara-toggle-label")?.textContent || "Setting";
      toast(`${label}: ${on ? "on" : "off"} (demo)`);
    });
  });

  document.querySelectorAll(".eara-anc-list .eara-chip, .eara-eq-grid .eara-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const group = chip.parentElement;
      group.querySelectorAll(".eara-chip").forEach((c) => c.classList.remove("eara-chip-active"));
      chip.classList.add("eara-chip-active");
      toast(`${chip.textContent} (demo)`);
    });
  });

  document.getElementById("btn-refresh")?.addEventListener("click", () => toast("Refresh (demo)"));

  ["btn-ring-l", "btn-ring-r", "btn-ring", "btn-ring-off"].forEach((id) => {
    document.getElementById(id)?.addEventListener("click", () => toast(`${id.replace("btn-ring", "Ring")} (demo)`));
  });

  document.getElementById("btn-disconnect")?.addEventListener("click", () => {
    document.getElementById("status-dot")?.classList.replace("eara-dot-ok", "eara-dot-off");
    document.getElementById("status-name").textContent = "Disconnected";
    document.getElementById("status-meta").textContent = "Tap Connect in the header";
    toast("Disconnected (demo)");
  });

  document.getElementById("hdr-connect")?.addEventListener("click", () => {
    document.getElementById("status-dot")?.classList.replace("eara-dot-off", "eara-dot-ok");
    document.getElementById("status-name").textContent = "Nothing Ear (a)";
    document.getElementById("status-meta").textContent =
      "Connected · Nothing Ear (a) · fw 1.0.1.51 · SN10832421008835";
    toast("Connected (demo)");
  });

  document.getElementById("hdr-reset")?.addEventListener("click", () => toast("Reset link (demo)"));

  const bandsEl = document.getElementById("eq-bands");
  if (bandsEl) {
    [32, 64, 125, 250, 500, 1000, 2000, 4000].forEach((hz) => {
      const wrap = document.createElement("div");
      wrap.className = "eara-eq-band";
      const input = document.createElement("input");
      input.type = "range";
      input.min = "-6";
      input.max = "6";
      input.value = "0";
      input.addEventListener("input", () => toast(`${hz >= 1000 ? hz / 1000 + "k" : hz}Hz: ${input.value} dB`));
      const label = document.createElement("label");
      label.textContent = hz >= 1000 ? `${hz / 1000}k` : String(hz);
      wrap.appendChild(input);
      wrap.appendChild(label);
      bandsEl.appendChild(wrap);
    });
  }
})();
