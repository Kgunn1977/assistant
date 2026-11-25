/* How the page reaches its data on the owner's site: same-site requests that carry their sign-in.
   It keeps one line open to the site, which answers the moment anything changes, so new items
   and results show by themselves. If the site will not hold a line open, it asks every 2 seconds. */
window.LIVE_STORE = function () {
  'use strict';
  var csrf = '', etag = '', onLive, onAnswers, onTrouble, busy = false, again = 0, listening;
  function api(path, opts) {
    opts = opts || {};
    opts.credentials = 'same-origin'; opts.cache = 'no-store';
    return fetch('api/' + path, opts);
  }
  function next(ms) {
    clearTimeout(again);
    again = setTimeout(function () { if (!document.hidden) pull(); }, ms);
  }
  function pull() {
    if (busy) return;
    busy = true;
    var began = Date.now(), head = etag ? {'X-Brief-Have': etag, 'X-Brief-Wait': '1'} : {};
    api('data', {headers: head}).then(function (r) {
      if (r.status === 401) { location.reload(); return null; }
      if (r.status === 304) { onLive(null, true, listening); return null; }
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    }).then(function (j) {
      busy = false;
      if (j) {
        csrf = j.csrf || '';
        etag = j.etag || '';          /* carried in the reply itself: the host strips the usual header */
        listening = j.listening;
        onLive(j.live || {}, true, listening);
        onAnswers(j.answers || {});
      }
      /* A line that was not held: ask again in 2 seconds. Never ask more than about twice a second. */
      next(!j && Date.now() - began < 1500 ? 2000 : Math.max(50, 500 - (Date.now() - began)));
    }, function () {
      busy = false;
      onTrouble('The data cannot be reached right now, so this may be out of date.', false);
      next(4000);
    });
  }
  function post(path, body) {
    return api(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Brief-Csrf': csrf}, body: JSON.stringify(body)})
      .then(function (r) {
        if (r.status === 401) { location.reload(); }
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      });
  }
  return Promise.resolve({
    watch: function (live, answers, trouble) {
      var last = {};
      onLive = function (docs, sure, hears) { if (docs) last = docs; live(last, sure, hears); };
      onAnswers = answers; onTrouble = trouble;
      pull();
      setInterval(function () { if (!document.hidden && !busy) pull(); }, 30000);
      document.addEventListener('visibilitychange', function () { if (!document.hidden) pull(); });
    },
    setAnswer: function (key, rec) { return post('answer', {key: key, record: rec}); },
    clearAnswer: function (key) { return post('answer', {key: key, record: null}); },
    signOut: function () { return post('logout', {}).then(function () { location.reload(); }, function () { location.reload(); }); },
    /* the page's own server only: the password never goes anywhere else */
    changePassword: function (current, fresh, again) { return post('password', {current: current, 'new': fresh, again: again}); },
    signOutAll: function () { return post('signout_all', {}).then(function () { location.reload(); }, function () { location.reload(); }); }
  });
};
