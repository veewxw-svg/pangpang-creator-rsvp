self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open("pangpang-kol-rsvp-v1").then((cache) => cache.addAll(["./index.html", "./manifest.webmanifest"]))
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request).then((cached) => cached || caches.match("./index.html")))
  );
});
