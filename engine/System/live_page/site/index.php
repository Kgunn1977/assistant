<?php
declare(strict_types=1);
/* The live page. This one file answers every address under its folder.
   Nothing is shown and no data is served without a signed-in session, except the feed
   door, which takes only the engine's key and can only write the feed and read answers. */

const DATA = __DIR__ . '/data';
const APP = __DIR__ . '/app';
const GUARD = "<?php http_response_code(404); exit; ?>\n";   // first line of every data file
const COOKIE = '__Secure-brief';
const SESSION_SECONDS = 90 * 86400;   // how long a sign-in lasts unless the owner chose another length in Settings
const WINDOW = 900;          // wrong tries are counted over 15 minutes
const IP_TRIES = 5;          // wrong passwords from one address before it is locked out
const ALL_TRIES = 20;        // wrong passwords from anywhere before everyone is locked out
const KEY_TRIES = 10;        // wrong feed keys from one address before it is locked out
const MAX_BODY = 6000000;
const MIN_PASSWORD = 10;
const HOLD_ENGINE = 25;      // seconds the computer's line is held open waiting for an answer
const HOLD_PAGE = 20;        // seconds an open page's line is held open waiting for a change
const LISTENING_FOR = 45;    // the computer counts as listening this long after it last held its line

$base = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/index.php')), '/');
define('BASE', $base);

function is_https(): bool {
    return (($_SERVER['HTTPS'] ?? '') !== '' && $_SERVER['HTTPS'] !== 'off')
        || ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https'
        || (int)($_SERVER['SERVER_PORT'] ?? 0) === 443;
}

function common_headers(): void {
    header_remove('X-Powered-By');
    header('Cache-Control: no-store, private, max-age=0');
    header('Pragma: no-cache');
    header('Expires: 0');
    header('X-Robots-Tag: noindex, nofollow, noarchive, nosnippet');
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header('Referrer-Policy: same-origin');
    header('Cross-Origin-Opener-Policy: same-origin');
    header('Cross-Origin-Resource-Policy: same-origin');
    header('Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()');
    header("Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        . "font-src https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data:; form-action 'self'; "
        . "base-uri 'none'; frame-ancestors 'none'");
}

function e(string $s): string { return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
/* The page's own title, as the owner's computer last sent it with the page's data; a plain one until then. */
function desk_title(): string {
    $f = load('feed'); $t = $f['docs']['current']['page_title'] ?? '';
    return is_string($t) && trim($t) !== '' ? substr(trim($t), 0, 80) : 'Your desk';
}
/* The name a password manager files the sign-in under: the first word of the title, in small letters. */
function desk_user(): string {
    return preg_match('/^[A-Za-z]+/', desk_title(), $m) ? strtolower($m[0]) : 'owner';
}

function json_out(int $code, array $body, array $extra = []): never {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    foreach ($extra as $h) header($h);
    echo json_encode($body, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP);
    exit;
}

/* ---------- storage: JSON behind a line that stops PHP, in a folder the web is refused ---------- */
function load(string $name): array {
    $f = DATA . "/$name.php";
    if (!is_file($f)) return [];
    $t = (string)file_get_contents($f);
    $j = json_decode(substr($t, strlen(GUARD)), true);
    return is_array($j) ? $j : [];
}
function save(string $name, array $d): void {
    $f = DATA . "/$name.php";
    $tmp = DATA . "/$name." . bin2hex(random_bytes(6)) . '.tmp.php';
    file_put_contents($tmp, GUARD . json_encode($d, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE), LOCK_EX);
    @chmod($tmp, 0600);
    rename($tmp, $f);
}
function locked(callable $fn) {
    $h = fopen(DATA . '/lock.php', 'c');
    flock($h, LOCK_EX);
    try { return $fn(); } finally { flock($h, LOCK_UN); fclose($h); }
}
function ip(): string { return (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown'); }

/* ---------- counting wrong tries ---------- */
function wait_seconds(string $bucket, int $ipMax, int $allMax): int {
    $t = load('throttle'); $now = time(); $b = $t[$bucket] ?? [];
    $mine = array_values(array_filter($b['ip'][ip()] ?? [], fn($x) => $x > $now - WINDOW));
    $all = array_values(array_filter($b['all'] ?? [], fn($x) => $x > $now - WINDOW));
    $wait = 0;
    if (count($mine) >= $ipMax) $wait = max($wait, $mine[count($mine) - $ipMax] + WINDOW - $now);
    if ($allMax && count($all) >= $allMax) $wait = max($wait, $all[count($all) - $allMax] + WINDOW - $now);
    return max(0, $wait);
}
function count_wrong(string $bucket): void {
    locked(function () use ($bucket) {
        $t = load('throttle'); $now = time(); $b = $t[$bucket] ?? ['ip' => [], 'all' => [], 'total' => 0];
        foreach ($b['ip'] as $k => $v) {
            $b['ip'][$k] = array_values(array_filter($v, fn($x) => $x > $now - WINDOW));
            if (!$b['ip'][$k]) unset($b['ip'][$k]);
        }
        $b['all'] = array_values(array_filter($b['all'], fn($x) => $x > $now - WINDOW));
        $b['ip'][ip()][] = $now; $b['all'][] = $now;
        $b['total'] = (int)($b['total'] ?? 0) + 1; $b['last'] = date('c', $now); $b['last_from'] = ip();
        $t[$bucket] = $b; save('throttle', $t);
    });
}
function clear_wrong(string $bucket): void {
    locked(function () use ($bucket) {
        $t = load('throttle');
        if (isset($t[$bucket]['ip'][ip()])) { unset($t[$bucket]['ip'][ip()]); save('throttle', $t); }
    });
}

/* ---------- sessions ---------- */
/* How long a new sign-in lasts: the owner's choice in Settings, as their computer last sent it with the
   page's data, else 90 days. */
function session_seconds(): int {
    $f = load('feed'); $d = $f['docs']['current']['settings']['signin']['days'] ?? null;
    return in_array($d, [1, 7, 30, 90], true) ? $d * 86400 : SESSION_SECONDS;
}
function put_cookie(string $token, int $expires): void {
    setcookie(COOKIE, $token, ['expires' => $expires, 'path' => BASE . '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
}
function session(): ?array {
    $tok = $_COOKIE[COOKIE] ?? '';
    if (!is_string($tok) || strlen($tok) < 40 || strlen($tok) > 200) return null;
    $id = hash('sha256', $tok); $now = time(); $all = load('sessions');
    if (!isset($all[$id]) || ($all[$id]['exp'] ?? 0) < $now) return null;
    if ($now - ($all[$id]['seen'] ?? 0) > 86400) {        // slide the sign-in's own length forward, once a day
        $len = (int)($all[$id]['len'] ?? SESSION_SECONDS);
        locked(function () use ($id, $now, $len) {
            $all = load('sessions');
            if (isset($all[$id])) { $all[$id]['seen'] = $now; $all[$id]['exp'] = $now + $len; save('sessions', $all); }
        });
        put_cookie($tok, $now + $len);
    }
    return $all[$id] + ['id' => $id];
}
function open_session(): void {
    $tok = rtrim(strtr(base64_encode(random_bytes(48)), '+/', '-_'), '=');
    $now = time(); $len = session_seconds();
    locked(function () use ($tok, $now, $len) {
        $all = array_filter(load('sessions'), fn($s) => ($s['exp'] ?? 0) > $now);
        uasort($all, fn($a, $b) => ($b['seen'] ?? 0) <=> ($a['seen'] ?? 0));
        $all = array_slice($all, 0, 19, true);           // at most 20 devices signed in
        $all[hash('sha256', $tok)] = ['made' => $now, 'seen' => $now, 'exp' => $now + $len, 'len' => $len,
            'csrf' => bin2hex(random_bytes(32))];
        save('sessions', $all);
    });
    put_cookie($tok, $now + $len);
}
function close_session(string $id): void {
    locked(function () use ($id) { $all = load('sessions'); unset($all[$id]); save('sessions', $all); });
    setcookie(COOKIE, '', ['expires' => 1, 'path' => BASE . '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
}
function same_origin(): bool {
    $o = $_SERVER['HTTP_ORIGIN'] ?? '';
    if ($o === '') return true;                           // not sent by this browser; the session check still applies
    return hash_equals('https://' . ($_SERVER['HTTP_HOST'] ?? ''), $o);
}
function body_json(): array {
    $raw = (string)file_get_contents('php://input', false, null, 0, MAX_BODY + 1);
    if (strlen($raw) > MAX_BODY) json_out(413, ['error' => 'too large']);
    $j = json_decode($raw, true);
    if (!is_array($j)) json_out(400, ['error' => 'not understood']);
    return $j;
}

/* ---------- pages ---------- */
function page_head(string $title, array $css, array $js): string {
    $o = '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        . '<meta name="robots" content="noindex,nofollow,noarchive"><meta name="referrer" content="same-origin">'
        . '<title>' . e($title) . '</title>'
        . '<link rel="preconnect" href="https://fonts.googleapis.com">'
        . '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&amp;family=IBM+Plex+Sans+Condensed:wght@500;600;700&amp;family=IBM+Plex+Sans:wght@400;500;600&amp;display=swap">';
    foreach ($css as $c) $o .= '<link rel="stylesheet" href="' . e(BASE . '/s/' . $c) . '">';
    foreach ($js as $j) $o .= '<script src="' . e(BASE . '/s/' . $j) . '" defer></script>';
    return $o . '</head><body>';
}
function sign_in_page(string $say = '', int $code = 200): never {
    http_response_code($code);
    header('Content-Type: text/html; charset=utf-8');
    echo page_head('Sign in', ['login.css'], []);
    echo '<main class="box"><h1>' . e(desk_title()) . '</h1><p class="sub">Sign in to open the page.</p>';
    if ($say !== '') echo '<p class="say" role="alert">' . e($say) . '</p>';
    echo '<form method="post" action="' . e(BASE . '/login') . '" autocomplete="on">'
        . '<input type="text" name="username" value="' . e(desk_user()) . '" autocomplete="username" hidden>'
        . '<label for="p">Password</label><input id="p" type="password" name="password" autocomplete="current-password" required autofocus>'
        . '<button type="submit">Sign in</button></form></main></body></html>';
    exit;
}
function setup_page(string $say = ''): never {
    header('Content-Type: text/html; charset=utf-8');
    echo page_head('Set your password', ['login.css'], ['login.js']);
    echo '<main class="box"><h1>' . e(desk_title()) . '</h1><p class="sub">Choose the password for this page. This address works once.</p>';
    if ($say !== '') echo '<p class="say" role="alert">' . e($say) . '</p>';
    echo '<form method="post" action="' . e(BASE . '/setup') . '" id="setup" autocomplete="on">'
        . '<input type="hidden" name="token" id="token">'
        . '<input type="text" name="username" value="' . e(desk_user()) . '" autocomplete="username" hidden>'
        . '<label for="p1">New password, ' . MIN_PASSWORD . ' characters or more</label><input id="p1" type="password" name="password" autocomplete="new-password" minlength="' . MIN_PASSWORD . '" required autofocus>'
        . '<label for="p2">The same password again</label><input id="p2" type="password" name="again" autocomplete="new-password" minlength="' . MIN_PASSWORD . '" required>'
        . '<button type="submit">Set password and sign in</button></form></main></body></html>';
    exit;
}
function serve(string $file, string $type): never {
    $f = APP . '/' . $file;
    if (!is_file($f)) { http_response_code(404); exit; }
    header("Content-Type: $type; charset=utf-8");
    readfile($f);
    exit;
}
/* The files this page is made of, checked against the list made when they were built,
   so a file damaged on its way to the site is noticed instead of half-working. */
function damaged_files(): array {
    $list = json_decode((string)@file_get_contents(APP . '/manifest.json'), true);
    if (!is_array($list)) return ['manifest.json'];
    $bad = [];
    foreach ($list as $name => $want) {
        $f = $name === 'index.php' ? __FILE__ : APP . '/' . basename((string)$name);
        $have = is_file($f) ? hash('sha256', str_replace("\r", '', (string)file_get_contents($f))) : '';
        if (!hash_equals((string)$want, $have)) $bad[] = (string)$name;
    }
    return $bad;
}
/* ---------- held-open lines: who is listening, and what changed ---------- */
function hold_seconds(int $normal): int {
    $h = getenv('BRIEF_HOLD');                             // tests only: 0 turns holding off
    return $h === false ? $normal : max(0, (int)$h);
}
function listening(): bool {
    clearstatcache(true, DATA . '/listener.php');
    $t = @filemtime(DATA . '/listener.php');
    return $t !== false && time() - $t < LISTENING_FOR;
}
function page_etag(string $csrf): string {
    clearstatcache();
    return '"' . sha1((string)@filemtime(DATA . '/feed.php') . '|' . (string)@filemtime(DATA . '/answers.php') . '|'
        . (string)@filesize(DATA . '/answers.php') . '|' . (listening() ? 'L' : 'A') . '|' . $csrf) . '"';
}
/* The engine marks how far it has got with an answer; only the answer it names (same `at`) is marked. */
function apply_marks(array &$items, array $marks): bool {
    $changed = false;
    foreach ($marks as $m) {
        if (!is_array($m) || !isset($m[0], $m[1], $m[2], $items[$m[0]]) || ($items[$m[0]]['at'] ?? '') !== $m[1]) continue;
        if (!in_array($m[2], ['working', 'done', 'failed'], true)) continue;
        $items[$m[0]]['status'] = $m[2];
        $items[$m[0]]['outcome'] = is_string($m[3] ?? null) ? substr($m[3], 0, 2000) : '';
        $items[$m[0]]['as_of'] = is_string($m[4] ?? null) ? substr($m[4], 0, 40) : '';   // how new the item must be to match this result
        $changed = true;
    }
    return $changed;
}
function mark_progress(array $marks): void {
    locked(function () use ($marks) {
        $a = load('answers'); $items = $a['items'] ?? [];
        if (apply_marks($items, $marks)) save('answers', ['v' => (int)($a['v'] ?? 0) + 1, 'av' => (int)($a['av'] ?? 0), 'items' => $items, 'undone' => $a['undone'] ?? []]);
    });
}
function setup_open(array $cfg): bool {
    return isset($cfg['setup']['hash']) && ($cfg['setup']['exp'] ?? 0) > time();
}

/* ---------- the feed door: the engine's key only ---------- */
function feed_key_or_refuse(array $cfg): void {
    $wait = wait_seconds('feed', KEY_TRIES, 0);
    if ($wait > 0) json_out(429, ['error' => 'locked', 'retry_in' => $wait], ["Retry-After: $wait"]);
    $key = (string)($_SERVER['HTTP_X_BRIEF_KEY'] ?? '');
    if (!isset($cfg['feed_key']) || $key === '' || !hash_equals((string)$cfg['feed_key'], hash('sha256', $key))) {
        count_wrong('feed');
        usleep(400000);
        json_out(403, ['error' => 'refused']);
    }
}

/* ================= request ================= */
common_headers();
if (!is_https()) {
    header('Location: https://' . ($_SERVER['HTTP_HOST'] ?? 'localhost') . ($_SERVER['REQUEST_URI'] ?? BASE . '/'), true, 301);
    exit;
}
$path = (string)parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
$route = trim(substr($path, strlen(BASE)), '/');
if ($route === 'index.php') $route = '';
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$cfg = load('config');

/* engine side */
if ($route === 'api/feed' && $method === 'POST') {
    feed_key_or_refuse($cfg);
    $in = body_json();
    if (!isset($in['docs']['current']['built']) || !is_array($in['docs'])) json_out(400, ['error' => 'no feed in the request']);
    $out = locked(function () use ($in) {
        save('feed', ['docs' => $in['docs'], 'received' => date('c')]);
        $a = load('answers'); $items = $a['items'] ?? []; $changed = false;
        foreach (($in['clear'] ?? []) as $c) {
            if (is_array($c) && isset($c[0], $c[1], $items[$c[0]]) && ($items[$c[0]]['at'] ?? '') === $c[1]) { unset($items[$c[0]]); $changed = true; }
        }
        // The items and the result that goes with them land together, so no reader sees one without the other.
        if (is_array($in['progress'] ?? null) && apply_marks($items, $in['progress'])) $changed = true;
        if ($changed) save('answers', ['v' => (int)($a['v'] ?? 0) + 1, 'av' => (int)($a['av'] ?? 0), 'items' => $items, 'undone' => $a['undone'] ?? []]);
        $back = load('feed');
        return ['ok' => true, 'built' => $back['docs']['current']['built'] ?? null, 'stamp' => $back['docs']['current']['stamp'] ?? null,
            'answers' => (object)$items];
    });
    $t = load('throttle');
    $out['wrong_keys'] = (int)($t['feed']['total'] ?? 0);
    $out['damaged_files'] = damaged_files();
    json_out(200, $out);
}
if ($route === 'api/progress' && $method === 'POST') {
    feed_key_or_refuse($cfg);
    $in = body_json();
    mark_progress(is_array($in['marks'] ?? null) ? $in['marks'] : []);
    json_out(200, ['ok' => true]);
}
/* The computer's line: held open until the owner answers something, or the hold time runs out. */
if ($route === 'api/wait' && $method === 'GET') {
    feed_key_or_refuse($cfg);
    $since = (int)($_SERVER['HTTP_X_BRIEF_SINCE'] ?? -1);
    $hold = hold_seconds(HOLD_ENGINE);
    @set_time_limit($hold + 20);
    $until = microtime(true) + $hold; $beat = 0;
    while (true) {
        if (time() - $beat >= 10) { @touch(DATA . '/listener.php'); $beat = time(); }
        $a = load('answers'); $av = (int)($a['av'] ?? 0);
        if ($av !== $since || microtime(true) >= $until || connection_aborted()) break;
        usleep(250000);
    }
    @touch(DATA . '/listener.php');
    json_out(200, ['ok' => true, 'av' => $av, 'changed' => $av !== $since, 'held' => $hold, 'answers' => (object)($a['items'] ?? []),
        'undone' => (object)($a['undone'] ?? [])]);
}
if ($route === 'api/answers' && $method === 'GET' && isset($_SERVER['HTTP_X_BRIEF_KEY'])) {
    feed_key_or_refuse($cfg);
    $a = load('answers');
    json_out(200, ['ok' => true, 'answers' => (object)($a['items'] ?? [])]);
}
/* The page's own files. The engine's key may replace these four and no others: never this file,
   the sign-in files, the stored data, or anything outside the app folder. The version before is
   kept, and "restore" puts it back. A name not on the list refuses the whole request. */
if ($route === 'api/files' && $method === 'POST') {
    feed_key_or_refuse($cfg);
    $allowed = ['app.css', 'app.js', 'shell.html', 'manifest.json'];
    $in = body_json();
    $new = $in['files'] ?? [];
    if (!empty($in['restore'])) {
        $p = load('prior_files'); $new = $p['files'] ?? [];
        if (!$new) json_out(409, ['error' => 'nothing to restore']);
    }
    if (!is_array($new)) json_out(400, ['error' => 'not understood']);
    foreach ($new as $name => $text) {
        if (!is_string($name) || !in_array($name, $allowed, true) || !is_string($text) || strlen($text) > 1500000)
            json_out(400, ['error' => 'refused', 'file' => is_string($name) ? substr($name, 0, 80) : '']);
    }
    $out = locked(function () use ($new) {
        $prior = [];
        foreach ($new as $name => $text) { $f = APP . '/' . $name; if (is_file($f)) $prior[$name] = (string)file_get_contents($f); }
        if ($new) save('prior_files', ['at' => date('c'), 'files' => $prior]);
        foreach ($new as $name => $text) {
            $f = APP . '/' . $name; $tmp = $f . '.' . bin2hex(random_bytes(6)) . '.tmp';
            if (file_put_contents($tmp, $text, LOCK_EX) === false || !rename($tmp, $f)) { @unlink($tmp); return ['ok' => false, 'error' => 'could not write ' . $name]; }
        }
        return ['ok' => true, 'replaced' => array_keys($new)];
    });
    clearstatcache();
    $out['hashes'] = [];
    foreach ($allowed as $name) {
        $f = APP . '/' . $name;
        $out['hashes'][$name] = is_file($f) ? hash('sha256', str_replace("\r", '', (string)file_get_contents($f))) : '';
    }
    $out['damaged_files'] = damaged_files();
    json_out($out['ok'] ? 200 : 500, $out);
}

/* sign-in, setup */
if ($route === 'login' && $method === 'POST') {
    if (!same_origin()) sign_in_page('That request did not come from this page.', 403);
    $wait = wait_seconds('login', IP_TRIES, ALL_TRIES);
    if ($wait > 0) { header("Retry-After: $wait"); sign_in_page('Too many wrong passwords. Try again in ' . (int)ceil($wait / 60) . ' minutes.', 429); }
    $pw = (string)($_POST['password'] ?? '');
    if (isset($cfg['pass']) && $pw !== '' && strlen($pw) <= 1000 && password_verify($pw, (string)$cfg['pass'])) {
        clear_wrong('login');
        open_session();
        header('Location: ' . BASE . '/', true, 303);
        exit;
    }
    count_wrong('login');
    sleep(1);
    sign_in_page('That password is not right.', 401);
}
if ($route === 'setup') {
    if (!setup_open($cfg)) sign_in_page($method === 'POST' ? 'That setup address has already been used.' : '');
    if ($method !== 'POST') setup_page();
    if (!same_origin()) setup_page('That request did not come from this page.');
    $wait = wait_seconds('login', IP_TRIES, ALL_TRIES);
    if ($wait > 0) { http_response_code(429); setup_page('Too many wrong tries. Try again in ' . (int)ceil($wait / 60) . ' minutes.'); }
    $tok = (string)($_POST['token'] ?? ''); $pw = (string)($_POST['password'] ?? '');
    if ($tok === '' || !hash_equals((string)$cfg['setup']['hash'], hash('sha256', $tok))) {
        count_wrong('login'); sleep(1);
        setup_page('This is not the setup address you were given. Open the full address again.');
    }
    if (strlen($pw) < MIN_PASSWORD || strlen($pw) > 1000) setup_page('Use ' . MIN_PASSWORD . ' characters or more.');
    if ($pw !== (string)($_POST['again'] ?? '')) setup_page('The two passwords do not match.');
    locked(function () use ($pw) {
        $cfg = load('config');
        $cfg['pass'] = password_hash($pw, PASSWORD_DEFAULT, ['cost' => 12]);
        $cfg['pass_set'] = date('c');
        unset($cfg['setup']);                              // the setup address stops working here
        save('config', $cfg);
        save('sessions', []);                              // any earlier sign-in ends
    });
    open_session();
    header('Location: ' . BASE . '/', true, 303);
    exit;
}
if ($route === 's/login.css') serve('login.css', 'text/css');
if ($route === 's/login.js') serve('login.js', 'text/javascript');

/* everything below needs a signed-in session */
$s = session();
if ($s === null) {
    if (str_starts_with($route, 'api/')) json_out(401, ['error' => 'sign in']);
    if ($route !== '') { header('Location: ' . BASE . '/', true, 303); exit; }
    sign_in_page();
}
if ($route === 's/app.css') serve('app.css', 'text/css');
if ($route === 's/app.js') serve('app.js', 'text/javascript');

if ($route === 'api/data' && $method === 'GET') {
    $have = (string)($_SERVER['HTTP_X_BRIEF_HAVE'] ?? $_SERVER['HTTP_IF_NONE_MATCH'] ?? '');   // the host strips ETag, so the page sends what it holds in its own header
    $etag = page_etag($s['csrf']);
    if ($have === $etag && ($_SERVER['HTTP_X_BRIEF_WAIT'] ?? '') === '1') {      // hold the page's line open until something changes
        $hold = hold_seconds(HOLD_PAGE);
        @set_time_limit($hold + 20);
        $until = microtime(true) + $hold;
        while (microtime(true) < $until && !connection_aborted()) {
            usleep(300000);
            $etag = page_etag($s['csrf']);
            if ($etag !== $have) break;
        }
    }
    if ($have === $etag) { http_response_code(304); header("ETag: $etag"); exit; }
    [$feed, $a] = locked(fn() => [load('feed'), load('answers')]);     // one moment in time: never items from before a result with the result itself
    json_out(200, ['csrf' => $s['csrf'], 'etag' => $etag, 'listening' => listening(), 'live' => (object)($feed['docs'] ?? []),
        'answers' => (object)($a['items'] ?? [])], ["ETag: $etag"]);
}
if (in_array($route, ['api/answer', 'api/logout', 'api/password', 'api/signout_all'], true) && $method === 'POST') {
    if (!same_origin() || !hash_equals($s['csrf'], (string)($_SERVER['HTTP_X_BRIEF_CSRF'] ?? ''))) json_out(403, ['error' => 'refused']);
    if ($route === 'api/logout') { close_session($s['id']); json_out(200, ['ok' => true]); }
    if ($route === 'api/signout_all') {                   // every sign-in on this page ends, this browser's too
        locked(function () { save('sessions', []); });
        setcookie(COOKIE, '', ['expires' => 1, 'path' => BASE . '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
        json_out(200, ['ok' => true]);
    }
    if ($route === 'api/password') {                      // the present password, then the new one twice; never logged
        $in = body_json();
        $wait = wait_seconds('login', IP_TRIES, ALL_TRIES);
        if ($wait > 0) json_out(200, ['ok' => false, 'error' => 'Too many wrong passwords. Try again in ' . (int)ceil($wait / 60) . ' minutes.']);
        $cur = is_string($in['current'] ?? null) ? $in['current'] : '';
        $new = is_string($in['new'] ?? null) ? $in['new'] : '';
        $again = is_string($in['again'] ?? null) ? $in['again'] : '';
        if (!isset($cfg['pass']) || $cur === '' || strlen($cur) > 1000 || !password_verify($cur, (string)$cfg['pass'])) {
            count_wrong('login');
            sleep(1);
            json_out(200, ['ok' => false, 'error' => 'The present password is not right.']);
        }
        if (strlen($new) < MIN_PASSWORD || strlen($new) > 1000) json_out(200, ['ok' => false, 'error' => 'Use ' . MIN_PASSWORD . ' characters or more for the new password.']);
        if ($new !== $again) json_out(200, ['ok' => false, 'error' => 'The two new passwords do not match.']);
        $mine = $s['id'];
        locked(function () use ($new, $mine) {
            $cfg = load('config');
            $cfg['pass'] = password_hash($new, PASSWORD_DEFAULT, ['cost' => 12]);
            $cfg['pass_set'] = date('c');
            save('config', $cfg);
            $all = load('sessions');                       // every other sign-in ends; this browser stays signed in
            save('sessions', isset($all[$mine]) ? [$mine => $all[$mine]] : []);
        });
        json_out(200, ['ok' => true]);
    }
    $in = body_json();
    $key = (string)($in['key'] ?? '');
    if (!preg_match('/^[A-Za-z0-9_\-.~:@+]{1,180}$/', $key)) json_out(400, ['error' => 'bad item']);
    $rec = $in['record'] ?? null; $clean = null;
    if (is_array($rec)) {
        $acts = ['approve', 'change', 'answer', 'done', 'later', 'snooze', 'reopen'];
        if (!in_array($rec['action'] ?? '', $acts, true)) json_out(400, ['error' => 'bad action']);
        $clean = ['sent' => false];
        foreach (['id', 'action', 'label', 'text', 'until', 'result', 'at', 'device', 'item_title', 'item_updated', 'open_card', 'button', 'meaning', 'pick'] as $f) {   // button, meaning: a choice's id and meaning, checked by the engine
            $v = $rec[$f] ?? null;
            $max = $f === 'text' ? 60000 : 4000;       // his words can be a whole email; every other field stays short
            if (is_string($v)) $clean[$f] = function_exists('mb_substr') ? mb_substr($v, 0, $max) : substr($v, 0, $max);
        }
        if (!isset($clean['at']) || !preg_match('/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/', $clean['at'])) $clean['at'] = date('Y-m-d\TH:i:s');
        if (!isset($clean['id'])) $clean['id'] = $key;
        $q = $rec['question'] ?? null;                      // the numbered question on the card this answer is for, as the local site keeps it
        if (is_int($q) && $q >= 1 && $q <= 20) $clean['question'] = $q;
        $r = $rec['redo'] ?? null;                          // Change on one answered question: its place among them
        if (is_int($r) && $r >= 1 && $r <= 20) $clean['redo'] = $r;
        if (is_array($rec['calendar'] ?? null)) {            // the day and time he picked for a calendar item
            $c = [];
            foreach (['title', 'date', 'start', 'end', 'location'] as $f) { $v = $rec['calendar'][$f] ?? null; $c[$f] = is_string($v) ? substr($v, 0, 300) : null; }
            if (!preg_match('/^\d{4}-\d\d-\d\d$/', (string)$c['date'])) json_out(400, ['error' => 'bad day']);
            foreach (['start', 'end'] as $f) if ($c[$f] !== null && !preg_match('/^\d\d:\d\d$/', $c[$f])) json_out(400, ['error' => 'bad time']);
            $c['all_day'] = !empty($rec['calendar']['all_day']);
            $c['accepted_as_shown'] = !empty($rec['calendar']['accepted_as_shown']);
            $clean['calendar'] = $c;
        }
        $clean['status'] = 'saved';                        // only the engine moves it on from here
    }
    locked(function () use ($key, $clean) {
        $a = load('answers'); $items = $a['items'] ?? [];
        // An Undo by the owner is remembered for 15 minutes so their computer can tell it from an answer the engine cleared.
        $undone = array_filter($a['undone'] ?? [], fn($u) => ($u['t'] ?? 0) > time() - 900);
        if ($clean === null) {
            if (isset($items[$key])) $undone[$key] = ['at' => (string)($items[$key]['at'] ?? ''), 't' => time()];
            unset($items[$key]);
        } else { $items[$key] = $clean; unset($undone[$key]); }
        save('answers', ['v' => (int)($a['v'] ?? 0) + 1, 'av' => (int)($a['av'] ?? 0) + 1, 'items' => $items, 'undone' => $undone]);
    });
    json_out(200, ['ok' => true]);
}
if ($route !== '') { header('Location: ' . BASE . '/', true, 303); exit; }

header('Content-Type: text/html; charset=utf-8');
echo page_head('Live Page', ['app.css'], ['app.js']);
readfile(APP . '/shell.html');
echo '</body></html>';
