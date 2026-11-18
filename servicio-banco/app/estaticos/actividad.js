/* La actividad humana renueva la sesión; los refrescos automáticos no. */
(function () {
  var limite = 10 * 60 * 1000;
  var clave = "ultima-actividad-" + location.host;
  var ultima = Date.now();
  var ultimoEnvio = 0;
  var pendiente = true;
  function guardar() {
    try { localStorage.setItem(clave, String(ultima)); } catch (e) {}
  }
  guardar();
  function salirSiVencio() {
    try { ultima = Math.max(ultima, Number(localStorage.getItem(clave)) || 0); } catch (e) {}
    if (Date.now() - ultima >= limite) {
      location.replace("/salir");
      return true;
    }
    return false;
  }
  function enviar() {
    if (salirSiVencio() || !pendiente || document.hidden) return;
    if (Date.now() - ultimoEnvio < 15000) return;
    ultimoEnvio = Date.now();
    pendiente = false;
    fetch("/sesion/actividad", {
      method: "POST", credentials: "same-origin", redirect: "manual",
      headers: {"X-Inactividad-Segundos": String(Math.max(0, (Date.now() - ultima) / 1000))}
    }).then(function (r) {
      if (r.status === 401 || r.status === 403 || r.type === "opaqueredirect") location.replace("/login");
      else if (!r.ok) pendiente = true;
    }).catch(function () { pendiente = true; });
  }
  ["pointerdown", "keydown", "scroll", "touchstart"].forEach(function (evento) {
    document.addEventListener(evento, function (e) {
      if (!e.isTrusted || salirSiVencio()) return;
      ultima = Date.now();
      guardar();
      pendiente = true;
      enviar();
    }, {passive: true});
  });
  window.addEventListener("storage", function (e) {
    if (e.key === clave) ultima = Math.max(ultima, Number(e.newValue) || 0);
  });
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) { salirSiVencio(); enviar(); }
  });
  setInterval(function () { if (!salirSiVencio()) enviar(); }, 1000);
})();
