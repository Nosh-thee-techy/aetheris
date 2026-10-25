export async function getJson(path, options) {
  const res = await fetch(path, options);
  return res.json();
}

export function me() {
  return getJson("/api/me");
}

export function desk() {
  return getJson("/api/desk");
}

export function enter(role, name) {
  return getJson("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, name }),
  });
}

export function leave() {
  return getJson("/api/logout", { method: "POST" });
}
