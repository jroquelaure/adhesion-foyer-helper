#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
foyer_app.py — Application « à fenêtre » (dans le navigateur) pour le Foyer Rural de Mondonville.
Aucune connaissance technique requise. Fonctionne sous macOS et Windows avec N'IMPORTE QUEL
Python 3 (y compris Homebrew) : elle n'utilise QUE la bibliothèque standard, pas de Tkinter,
rien à installer de plus.

Se lance par double-clic sur « Lancer (Mac).command » / « Lancer (Windows).bat »,
ou :  python3 foyer_app.py
Une page s'ouvre dans le navigateur. On remplit ses réglages une fois, puis on clique.
"""
import os, sys, json, threading, contextlib, traceback, webbrowser, subprocess, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import foyer_controle
import helloasso_export

HELLOASSO_JSON = os.path.join(BASE, "helloasso.json")
CONFIG_JSON = os.path.join(BASE, "config.json")
EXPORTS_DIR = os.path.join(BASE, "exports_api")
RESULTS_DIR = os.path.join(EXPORTS_DIR, "_resultats")

_LOCK = threading.Lock()
LOG = []            # liste de morceaux de texte
RUNNING = False
STATUS = "Prêt."


class _Writer:
    def write(self, s):
        if s:
            with _LOCK:
                LOG.append(s)
    def flush(self): pass


def _log(s):
    with _LOCK:
        LOG.append(s)


def charger_reglages():
    if os.path.isfile(HELLOASSO_JSON):
        try:
            return json.load(open(HELLOASSO_JSON, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def sauver_reglages(form):
    cfg = charger_reglages()
    for k in ("client_id", "organization_slug", "saison", "environnement"):
        if k in form:
            cfg[k] = form[k].strip()
    # la clé secrète n'est mise à jour que si un nouveau texte est saisi
    sec = (form.get("client_secret") or "").strip()
    if sec:
        cfg["client_secret"] = sec
    cfg.setdefault("environnement", "production")
    cfg.setdefault("types_formulaires", ["Membership", "Event"])
    json.dump(cfg, open(HELLOASSO_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def saison():
    return (charger_reglages().get("saison") or "").strip() or None


def _recuperer():
    for k in ("client_id", "client_secret", "organization_slug"):
        if not (charger_reglages().get(k) or "").strip():
            raise SystemExit("Réglages incomplets : renseignez identifiant, clé secrète et nom court, puis Enregistrer.")
    helloasso_export.run(HELLOASSO_JSON, EXPORTS_DIR, saison=saison())


def _analyser():
    if not os.path.isdir(EXPORTS_DIR) or not any(x.endswith(".csv") for x in os.listdir(EXPORTS_DIR)):
        raise SystemExit("Aucune donnée à analyser. Lancez d'abord « Récupérer depuis HelloAsso ».")
    cfg = CONFIG_JSON if os.path.isfile(CONFIG_JSON) else None
    foyer_controle.run(EXPORTS_DIR, RESULTS_DIR, (charger_reglages().get("saison") or "").strip(), cfg)


def _tout():
    _recuperer(); _analyser()


ACTIONS = {"fetch": _recuperer, "analyse": _analyser, "all": _tout}


def lancer(action):
    global RUNNING, STATUS
    with _LOCK:
        if RUNNING:
            return False
        RUNNING = True
        STATUS = "Traitement en cours… merci de patienter."
    fn = ACTIONS.get(action)

    def worker():
        global RUNNING, STATUS
        w = _Writer()
        _log("\n———————————————————————————\n")
        try:
            with contextlib.redirect_stdout(w), contextlib.redirect_stderr(w):
                fn()
            _log("\n✅ Terminé.\n"); STATUS = "Terminé."
        except SystemExit as e:
            _log("\n⛔ " + str(e) + "\n"); STATUS = "Arrêté — voir le journal."
        except Exception:
            _log("\n⛔ Une erreur est survenue :\n" + traceback.format_exc() + "\n"); STATUS = "Erreur — voir le journal."
        finally:
            with _LOCK:
                RUNNING = False

    threading.Thread(target=worker, daemon=True).start()
    return True


def ouvrir_resultats():
    if not os.path.isdir(RESULTS_DIR):
        return False
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", RESULTS_DIR])
        elif os.name == "nt":
            os.startfile(RESULTS_DIR)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", RESULTS_DIR])
        return True
    except Exception:
        return False


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Adhésions — Foyer Rural de Mondonville</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:0;background:#eef2f6;color:#1f2937}}
 .wrap{{max-width:840px;margin:0 auto;padding:18px}}
 h1{{font-size:20px;margin:6px 0 14px}}
 .card{{background:#fff;border:1px solid #dbe3ea;border-radius:12px;padding:16px;margin-bottom:16px}}
 .card h2{{font-size:15px;margin:0 0 12px;color:#1f3864}}
 label{{display:block;font-size:13px;margin:10px 0 4px;color:#374151}}
 input,select{{width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px}}
 .row{{display:flex;gap:12px;flex-wrap:wrap}} .row>div{{flex:1;min-width:220px}}
 button{{border:0;border-radius:9px;padding:11px 14px;font-size:14px;font-weight:600;cursor:pointer}}
 .primary{{background:#2e75b6;color:#fff}} .ghost{{background:#e5edf5;color:#1f3864}}
 .save{{background:#548235;color:#fff}}
 .actions{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
 #log{{background:#0f1720;color:#d7e2ec;border-radius:10px;padding:12px;height:280px;overflow:auto;white-space:pre-wrap;font-family:SFMono-Regular,Consolas,monospace;font-size:12.5px}}
 .status{{margin-top:8px;font-size:13px;color:#374151}}
 .hint{{font-size:12px;color:#6b7280;margin-top:4px}}
</style></head><body><div class="wrap">
<h1>Adhésions &amp; inscriptions — assistant</h1>

<div class="card"><h2>1 · Réglages HelloAsso (à remplir une seule fois)</h2>
 <div class="row">
  <div><label>Identifiant API (client_id)</label><input id="client_id" value="{client_id}"></div>
  <div><label>Nom court de l'association (dans l'URL HelloAsso)</label><input id="organization_slug" value="{slug}"></div>
 </div>
 <div class="row">
  <div><label>Clé secrète (client_secret)</label><input id="client_secret" type="password" placeholder="{secret_ph}"></div>
  <div><label>Saison</label><input id="saison" value="{saison}" placeholder="2025-2026"></div>
 </div>
 <div class="row">
  <div><label>Environnement</label><select id="environnement">
    <option value="production" {prod}>production</option>
    <option value="sandbox" {sand}>sandbox</option></select></div>
  <div style="align-self:end"><button class="save" onclick="save()">💾 Enregistrer les réglages</button></div>
 </div>
 <div class="hint">La clé secrète n'est affichée pour des raisons de sécurité ; laissez ce champ vide pour conserver celle déjà enregistrée.</div>
</div>

<div class="card"><h2>2 · Actions</h2>
 <div class="actions">
  <button class="primary" onclick="run('all')">▶ Tout faire</button>
  <button class="ghost" onclick="run('fetch')">1) Récupérer depuis HelloAsso</button>
  <button class="ghost" onclick="run('analyse')">2) Analyser &amp; préparer Gestanet</button>
  <button class="ghost" onclick="openResults()">📂 Ouvrir les résultats</button>
 </div>
 <div class="status" id="status">Prêt.</div>
</div>

<div class="card"><h2>Journal</h2><div id="log"></div></div>
</div>
<script>
 let from=0;
 function save(){{
   const b={{client_id:v('client_id'),client_secret:v('client_secret'),organization_slug:v('organization_slug'),
             saison:v('saison'),environnement:v('environnement')}};
   fetch('/api/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(b)}})
     .then(r=>r.json()).then(_=>{{document.getElementById('client_secret').value='';setStatus('Réglages enregistrés.');}});
 }}
 function run(w){{ fetch('/api/run?what='+w,{{method:'POST'}}); }}
 function openResults(){{ fetch('/api/open',{{method:'POST'}}).then(r=>r.json()).then(d=>{{if(!d.ok)setStatus('Aucun résultat pour l\\'instant — lancez d\\'abord l\\'analyse.');}}); }}
 function v(id){{return document.getElementById(id).value;}}
 function setStatus(s){{document.getElementById('status').textContent=s;}}
 function poll(){{
   fetch('/api/log?from='+from).then(r=>r.json()).then(d=>{{
     if(d.text){{const l=document.getElementById('log');l.textContent+=d.text;l.scrollTop=l.scrollHeight;from=d.next;}}
     setStatus(d.status);
   }}).catch(()=>{{}});
 }}
 setInterval(poll,900); poll();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            cfg = charger_reglages()
            page = PAGE.format(
                client_id=html.escape(cfg.get("client_id", "")),
                slug=html.escape(cfg.get("organization_slug", "")),
                saison=html.escape(cfg.get("saison", "")),
                secret_ph=("•••• déjà enregistrée" if cfg.get("client_secret") else "collez la clé secrète"),
                prod=("selected" if cfg.get("environnement", "production") != "sandbox" else ""),
                sand=("selected" if cfg.get("environnement") == "sandbox" else ""),
            )
            self._send(200, page, "text/html; charset=utf-8")
        elif u.path == "/api/log":
            frm = int((parse_qs(u.query).get("from", ["0"])[0]) or 0)
            with _LOCK:
                text = "".join(LOG[frm:]); nxt = len(LOG); status = STATUS
            self._send(200, json.dumps({"text": text, "next": nxt, "status": status}))
        else:
            self._send(404, json.dumps({"ok": False}))

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        if u.path == "/api/save":
            try:
                form = json.loads(raw.decode("utf-8") or "{}")
                sauver_reglages(form)
                self._send(200, json.dumps({"ok": True}))
            except Exception as e:
                self._send(200, json.dumps({"ok": False, "error": str(e)}))
        elif u.path == "/api/run":
            what = parse_qs(u.query).get("what", ["all"])[0]
            ok = lancer(what)
            self._send(200, json.dumps({"ok": ok}))
        elif u.path == "/api/open":
            self._send(200, json.dumps({"ok": ouvrir_resultats()}))
        else:
            self._send(404, json.dumps({"ok": False}))


def main():
    port = 8765
    httpd = None
    for p in range(8765, 8785):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), Handler); port = p; break
        except OSError:
            continue
    if httpd is None:
        print("Impossible de démarrer le serveur local."); return
    url = f"http://127.0.0.1:{port}/"
    print("Application démarrée : " + url)
    print("(Laissez cette fenêtre ouverte pendant l'utilisation. Fermez-la pour quitter.)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
