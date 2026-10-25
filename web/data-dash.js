/*
  Data-producer desk. Fills the ICPAC / Kenya Met page from GET /api/desk.

  The API reads the same repository files the generator uses. This script
  invents no radar yes/no, no rainfall total, and no chain state.
  Same-origin only. Open via python web/server.py — file:// cannot reach /api.
*/
(function () {
  "use strict";

  if (!document.body.classList.contains("skin-data")) return;

  var status = document.querySelector("[data-api-status]");

  function setStatus(cls, text) {
    if (!status) return;
    status.className = "api-status " + cls;
    status.textContent = text;
  }

  function text(sel, value) {
    var node = document.querySelector(sel);
    if (node) node.textContent = value;
  }

  function fill(desk) {
    var who = desk.viewer ? desk.viewer.label : "desk";
    setStatus(
      "ok",
      "Signed in as " + who + " · live from the local API · " + desk.places.length + " places · " + desk.week + ". " + desk.note
    );
    text("[data-api-rain-mm]", desk.rainfall.mm.toFixed(1) + " mm");
    text(
      "[data-api-rain-signed]",
      "Signed " + desk.rainfall.signed + " of " + desk.rainfall.places + ". " + desk.rainfall.scope + "."
    );
    text("[data-api-radar-assessed]", desk.radar.assessed + "/" + desk.radar.places);
    text(
      "[data-api-radar-line]",
      "Assessed " + desk.radar.assessed +
        ". Signed " + desk.radar.signed +
        ". Below the line " + desk.radar.below +
        ". No geometry " + desk.radar.no_geometry + "."
    );
    text("[data-api-rule-name]", desk.rule.name);
    text(
      "[data-api-rule]",
      "Frozen " + desk.rule.frozen_on + ". The hash on the chain is of this file, byte for byte."
    );

    var tbody = document.querySelector("[data-api-places] tbody");
    if (!tbody) return;
    tbody.textContent = "";
    desk.places.forEach(function (place) {
      var tr = document.createElement("tr");
      function cell(tag, value) {
        var node = document.createElement(tag);
        if (tag === "th") node.setAttribute("scope", "row");
        node.textContent = value;
        tr.appendChild(node);
      }
      var radarWord = "Not measured";
      if (place.radar === "yes") radarWord = "Signed";
      else if (place.radar === "no") radarWord = "Below the line";
      cell("th", place.name);
      cell("td", place.rainfall === "yes" ? "Signed" : "Did not sign");
      cell("td", radarWord);
      cell("td", place.land_pixels == null ? "—" : String(place.land_pixels));
      cell("td", place.flooded_pixels == null ? "—" : String(place.flooded_pixels));
      cell("td", place.has_outline ? "Outline" : "No outline");
      tbody.appendChild(tr);
    });
  }

  if (location.protocol === "file:") {
    setStatus(
      "bad",
      "This desk reads /api/desk. Run python web/server.py and open http://127.0.0.1:8765/for-data.html"
    );
    return;
  }

  fetch("/api/desk")
    .then(function (res) {
      if (res.status === 401) {
        setStatus("wait", "Enter a desk to connect the local API. The numbers below are from the page build.");
        return null;
      }
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (desk) { if (desk) fill(desk); })
    .catch(function (err) {
      setStatus("bad", "The local API did not answer. Run python web/server.py. " + err.message);
    });
})();
