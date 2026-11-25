/* Setup page only: the one-time code rides after the # in the address, which browsers never
   send to a server or write to its logs. Move it into the form, then wipe it from the address bar. */
(function () {
  var t = document.getElementById('token');
  if (!t) return;
  var code = location.hash.replace(/^#/, '');
  if (code) { t.value = code; try { history.replaceState(null, '', location.pathname); } catch (e) {} }
})();
