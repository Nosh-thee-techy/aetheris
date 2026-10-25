import L from "leaflet";
import "leaflet/dist/leaflet.css";

let map = null;
const layers = {};

function darkMap() {
  return document.documentElement.getAttribute("data-theme") === "dark";
}

function boxColor(place) {
  const dark = darkMap();
  if (place.tone === "go" || (!place.tone && place.radar === "yes")) return dark ? "#3ecfc8" : "#0d6e6a";
  if (place.tone === "hold") return dark ? "#e8a14a" : "#b05614";
  if (place.tone === "stop") return dark ? "#9aa3ab" : "#6b767c";
  return dark ? "#e07058" : "#9a2f1c";
}

export function mountKenyaMap(places, onPick) {
  const el = document.getElementById("kenya-map");
  if (!el) return;
  if (map) {
    map.remove();
    map = null;
  }
  Object.keys(layers).forEach((key) => delete layers[key]);

  map = L.map(el, { scrollWheelZoom: false }).setView([0.4, 37.9], 6);
  const tiles = darkMap()
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const attribution = darkMap()
    ? "&copy; OpenStreetMap &copy; CARTO"
    : "&copy; OpenStreetMap";
  L.tileLayer(tiles, { attribution, maxZoom: 18 }).addTo(map);

  const boxed = (places || []).filter((p) => p.zone);
  boxed.forEach((p) => {
    const bounds = [
      [p.zone.min_lat, p.zone.min_lon],
      [p.zone.max_lat, p.zone.max_lon],
    ];
    const rect = L.rectangle(bounds, {
      color: boxColor(p),
      weight: 2,
      fillOpacity: p.tone === "go" || p.radar === "yes" ? 0.4 : 0.18,
    }).addTo(map);
    rect.bindTooltip(p.name);
    rect.on("click", () => onPick(p.slug));
    layers[p.slug] = rect;
  });

  const kenya = document.querySelector("[data-zoom='kenya']");
  const basin = document.querySelector("[data-zoom='basin']");
  if (kenya) kenya.addEventListener("click", () => map.setView([0.4, 37.9], 6));
  if (basin && boxed.length) {
    basin.addEventListener("click", () => {
      const group = L.featureGroup(boxed.map((p) => layers[p.slug]));
      map.fitBounds(group.getBounds().pad(0.35));
    });
  }
}

export function focusBox(slug) {
  Object.entries(layers).forEach(([id, layer]) => {
    layer.setStyle({ weight: id === slug ? 4 : 2 });
  });
  if (map && layers[slug]) {
    map.fitBounds(layers[slug].getBounds().pad(0.6));
  }
}
