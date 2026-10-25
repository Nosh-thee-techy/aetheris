/*
  Desk gate. Landing → enter → dashboard.

  Demo access only: pick a role. No password, no accounts, no machine learning.
  Same-origin /api/session, /api/me, /api/logout. Open via python web/server.py.
*/
(function () {
  "use strict";

  var page = document.body.getAttribute("data-page");
  var whoBox = document.querySelector("[data-session]");
  var whoText = document.querySelector("[data-session-who]");
  var leave = document.querySelector("[data-leave]");
  var form = document.querySelector("[data-login]");
  var status = document.querySelector("[data-login-status]");
  var enters = document.querySelectorAll("[data-enter]");
  var themeBtn = document.querySelector("[data-theme]");

  function themeLabel(theme) {
    return theme === "dark" ? "White mode" : "Dark mode";
  }
  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("aetheris-theme", theme); } catch (e) { /* ignore */ }
    if (themeBtn) themeBtn.textContent = themeLabel(theme);
  }
  if (themeBtn) {
    themeBtn.textContent = themeLabel(currentTheme());
    themeBtn.addEventListener("click", function () {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }

  function fileNote(node) {
    if (!node) return;
    node.hidden = false;
    node.textContent = "Open this through python web/server.py — http://127.0.0.1:8765/";
  }

  function showStatus(node, cls, text) {
    if (!node) return;
    node.hidden = false;
    node.className = "api-status " + cls;
    node.textContent = text;
  }

  function showWho(who) {
    if (!whoBox || !whoText || !who) return;
    whoBox.hidden = false;
    whoText.textContent = (who.name ? who.name + " · " : "") + who.label;
  }

  function nextPage(who) {
    var next = new URLSearchParams(location.search).get("next") || "";
    if (/^[a-z0-9.-]+\.html$/.test(next)) return next;
    return who.home || "workspaces.html";
  }

  if (location.protocol === "file:") {
    if (form && status) {
      fileNote(status);
      status.className = "api-status bad";
      Array.prototype.forEach.call(form.querySelectorAll("button, input, select"), function (node) {
        node.disabled = true;
      });
    }
    return;
  }

  if (leave) {
    leave.addEventListener("click", function () {
      fetch("/api/logout", { method: "POST" }).finally(function () {
        location.href = "index.html";
      });
    });
  }

  function gateNote() {
    var host = document.getElementById("main");
    if (!host) return;
    var note = document.querySelector("[data-gate]");
    if (!note) {
      note = document.createElement("p");
      note.setAttribute("data-gate", "");
      note.className = "api-status wait";
      host.insertBefore(note, host.firstChild);
    }
    var here = (location.pathname.split("/").pop() || "workspaces.html");
    note.hidden = false;
    note.className = "api-status wait";
    note.innerHTML = 'This desk is open to read. To connect the live API, <a href="login.html?next=' + encodeURIComponent(here) + '">enter as your role</a>. No password.';
  }

  fetch("/api/me")
    .then(function (res) {
      if (res.status === 401) {
        if (page === "workspace") gateNote();
        return null;
      }
      if (!res.ok) return null;
      return res.json();
    })
    .then(function (who) {
      if (!who || !who.ok) return;
      showWho(who);
      Array.prototype.forEach.call(enters, function (link) {
        link.setAttribute("href", who.home);
        link.textContent = "Open your desk";
      });
      if (form) {
        showStatus(status, "ok", "You are already in as " + who.label + ". Open " + (who.home || "your desk") + " when you want.");
        var go = form.querySelector("[data-open-desk]");
        if (!go) {
          go = document.createElement("p");
          go.className = "cta";
          go.innerHTML = '<a class="btn primary" data-open-desk href="' + (who.home || "workspaces.html") + '">Open your desk</a>';
          form.appendChild(go);
        }
      }
    })
    .catch(function () {
      if (form) showStatus(status, "bad", "The local API did not answer. Run python web/server.py.");
    });

  if (!form) return;

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var data = new FormData(form);
    var role = data.get("role");
    if (!role) {
      showStatus(status, "bad", "Pick who you are.");
      return;
    }
    fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: String(role), name: String(data.get("name") || "") })
    })
      .then(function (res) { return res.json().then(function (body) { return { res: res, body: body }; }); })
      .then(function (pack) {
        if (!pack.res.ok || !pack.body.ok) {
          throw new Error(pack.body.error || "Could not enter");
        }
        location.href = nextPage(pack.body);
      })
      .catch(function (err) {
        showStatus(status, "bad", err.message);
      });
  });
})();
