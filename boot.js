// Offline boot for the published app, copied into dist/ by fix_no_cdn.py.
//
// Registers the precache worker, and holds Flet's loading overlay until Python
// has started: Flutter reveals the page at its first frame, which is blank
// while Pyodide and pandas load. Releases need no code here - the worker is
// named after the commit, installs on the next load, and the page then tells
// it to drop the previous release's cache.
//
// This runs in <head>, before the loading markup exists, so elements are
// looked up when they are needed rather than at parse time.

(() => {
  const RELEASE = "06cf3750ec8d";

  const fail = (error) => {
    const loading = document.getElementById("loading");
    if (loading) loading.textContent = `Could not start: ${error?.message ?? error}`;
  };

  const connect = globalThis.jsConnect;
  if (typeof connect === "function") {
    globalThis.jsConnect = async (...args) => {
      try {
        const result = await connect(...args);
        document.getElementById("loading")?.remove();
        return result;
      } catch (error) {
        fail(error);
        throw error;
      }
    };
  }

  // `updateViaCache: "none"` makes the browser revalidate sw.js itself, so a
  // deploy lands on the next load rather than up to 24 hours later.
  //
  // The purge drops the previous release's cache, but only once no worker is
  // installing: while one is, this page is still talking to the outgoing
  // worker, which would delete the incoming worker's half-filled cache. The
  // worker ignores a purge that is not for its own release, which covers the
  // other order - the message reaching the new worker instead.
  window.addEventListener("load", async () => {
    if (!navigator.serviceWorker) return;
    try {
      await navigator.serviceWorker.register("sw.js", { updateViaCache: "none" });
      const registration = await navigator.serviceWorker.ready;
      if (registration.installing || registration.waiting) return;
      registration.active?.postMessage({ purge: RELEASE });
    } catch (error) {
      console.warn("Offline cache unavailable:", error);
    }
  });
})();
