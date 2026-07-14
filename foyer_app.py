#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
foyer_app.py — Application « à fenêtre » pour le Foyer Rural de Mondonville.
Aucune connaissance technique requise : on remplit ses réglages une fois, puis on clique.
Fonctionne sous macOS et Windows (Tkinter est fourni avec Python).

Ce que fait l'application :
  1) « Récupérer depuis HelloAsso » : télécharge les adhésions/inscriptions via l'API.
  2) « Analyser & préparer Gestanet » : contrôle et génère les fichiers (dont ceux pour Gestanet).
  « Tout faire » enchaîne les deux.

Se lance par double-clic sur « Lancer (Mac).command » ou « Lancer (Windows).bat »,
ou en tapant :  python3 foyer_app.py
"""
import os, sys, json, queue, threading, traceback, subprocess, contextlib
import tkinter as tk
from tkinter import ttk, messagebox

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import foyer_controle
import helloasso_export

HELLOASSO_JSON = os.path.join(BASE, "helloasso.json")
CONFIG_JSON = os.path.join(BASE, "config.json")
EXPORTS_DIR = os.path.join(BASE, "exports_api")
RESULTS_DIR = os.path.join(EXPORTS_DIR, "_resultats")

CHAMPS = [
    ("client_id", "Identifiant API (client_id)"),
    ("client_secret", "Clé secrète (client_secret)"),
    ("organization_slug", "Nom court de l'association (dans l'URL HelloAsso)"),
    ("saison", "Saison (ex. 2025-2026)"),
]


class _Redirect:
    def __init__(self, q): self.q = q
    def write(self, s): self.q.put(s)
    def flush(self): pass


class App:
    def __init__(self, root):
        self.root = root
        root.title("Foyer Rural de Mondonville — Adhésions")
        root.geometry("860x660")
        self.q = queue.Queue()
        self.running = False
        self.vars = {}
        self._build()
        self._charger_reglages()
        self.root.after(120, self._vider_file)

    # ---------------- interface ----------------
    def _build(self):
        top = ttk.Label(self.root, text="Adhésions & inscriptions — assistant",
                        font=("Helvetica", 16, "bold"))
        top.pack(anchor="w", padx=12, pady=(12, 2))

        frm = ttk.LabelFrame(self.root, text="1 · Réglages HelloAsso  (à remplir une seule fois)")
        frm.pack(fill="x", padx=12, pady=8)
        for i, (key, label) in enumerate(CHAMPS):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            v = tk.StringVar(); self.vars[key] = v
            ttk.Entry(frm, textvariable=v, width=54,
                      show="*" if key == "client_secret" else "").grid(row=i, column=1, sticky="w", padx=8, pady=4)
        ttk.Label(frm, text="Environnement").grid(row=len(CHAMPS), column=0, sticky="w", padx=8, pady=4)
        self.vars["environnement"] = tk.StringVar(value="production")
        ttk.Combobox(frm, textvariable=self.vars["environnement"], values=["production", "sandbox"],
                     width=18, state="readonly").grid(row=len(CHAMPS), column=1, sticky="w", padx=8, pady=4)
        ttk.Button(frm, text="💾  Enregistrer les réglages",
                   command=self._enregistrer_reglages).grid(row=len(CHAMPS) + 1, column=1, sticky="e", padx=8, pady=6)

        act = ttk.LabelFrame(self.root, text="2 · Actions")
        act.pack(fill="x", padx=12, pady=8)
        self.btn_all = ttk.Button(act, text="▶  Tout faire", command=lambda: self._lancer(self._tout_faire))
        self.btn_all.pack(side="left", padx=(8, 6), pady=8)
        self.btn_fetch = ttk.Button(act, text="1) Récupérer depuis HelloAsso",
                                    command=lambda: self._lancer(self._recuperer))
        self.btn_fetch.pack(side="left", padx=6)
        self.btn_analyse = ttk.Button(act, text="2) Analyser & préparer Gestanet",
                                      command=lambda: self._lancer(self._analyser))
        self.btn_analyse.pack(side="left", padx=6)
        ttk.Button(act, text="📂  Ouvrir les résultats", command=self._ouvrir_resultats).pack(side="left", padx=6)

        logf = ttk.LabelFrame(self.root, text="Journal")
        logf.pack(fill="both", expand=True, padx=12, pady=8)
        self.log = tk.Text(logf, wrap="word", height=16, state="disabled",
                           bg="#0f1720", fg="#d7e2ec", insertbackground="#d7e2ec")
        self.log.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(logf, command=self.log.yview); sb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=sb.set)

        self.status = ttk.Label(self.root, text="Prêt.", anchor="w", relief="sunken")
        self.status.pack(fill="x", padx=12, pady=(0, 10))

    # ---------------- journal ----------------
    def _ecrire(self, s):
        self.log.configure(state="normal"); self.log.insert("end", s)
        self.log.see("end"); self.log.configure(state="disabled")

    def _vider_file(self):
        try:
            while True:
                self._ecrire(self.q.get_nowait())
        except queue.Empty:
            pass
        self.root.after(120, self._vider_file)

    # ---------------- réglages ----------------
    def _charger_reglages(self):
        if os.path.isfile(HELLOASSO_JSON):
            try:
                cfg = json.load(open(HELLOASSO_JSON, encoding="utf-8"))
                for k, v in self.vars.items():
                    if cfg.get(k) is not None:
                        v.set(str(cfg[k]))
            except Exception:
                pass

    def _reglages_dict(self):
        cfg = {}
        if os.path.isfile(HELLOASSO_JSON):
            try: cfg = json.load(open(HELLOASSO_JSON, encoding="utf-8"))
            except Exception: cfg = {}
        for k, v in self.vars.items():
            cfg[k] = v.get().strip()
        cfg.setdefault("types_formulaires", ["Membership", "Event"])
        return cfg

    def _sauver(self):
        json.dump(self._reglages_dict(), open(HELLOASSO_JSON, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    def _enregistrer_reglages(self):
        try:
            self._sauver()
            self.status.config(text="Réglages enregistrés.")
            messagebox.showinfo("Réglages", "Vos réglages ont été enregistrés.")
        except Exception as e:
            messagebox.showerror("Réglages", str(e))

    # ---------------- exécution ----------------
    def _actifs(self, on):
        self.running = on
        st = "disabled" if on else "normal"
        for b in (self.btn_all, self.btn_fetch, self.btn_analyse):
            b.configure(state=st)

    def _lancer(self, fn):
        if self.running:
            return
        try:
            self._sauver()
        except Exception:
            pass
        self._actifs(True)
        self.status.config(text="Traitement en cours… merci de patienter.")

        def worker():
            r = _Redirect(self.q)
            try:
                with contextlib.redirect_stdout(r), contextlib.redirect_stderr(r):
                    fn()
                self.q.put("\n✅ Terminé.\n")
                self.root.after(0, lambda: self.status.config(text="Terminé."))
            except SystemExit as e:
                self.q.put("\n⛔ " + str(e) + "\n")
                self.root.after(0, lambda: self.status.config(text="Arrêté — voir le journal."))
            except Exception:
                self.q.put("\n⛔ Une erreur est survenue :\n" + traceback.format_exc() + "\n")
                self.root.after(0, lambda: self.status.config(text="Erreur — voir le journal."))
            finally:
                self.root.after(0, lambda: self._actifs(False))

        threading.Thread(target=worker, daemon=True).start()

    def _saison(self):
        return self.vars["saison"].get().strip() or None

    def _verifier_reglages(self):
        for k in ("client_id", "client_secret", "organization_slug"):
            if not self.vars[k].get().strip():
                raise SystemExit("Réglages incomplets : renseignez client_id, client_secret et le nom court, "
                                 "puis « Enregistrer les réglages ».")

    def _recuperer(self):
        self._verifier_reglages()
        helloasso_export.run(HELLOASSO_JSON, EXPORTS_DIR, saison=self._saison())

    def _analyser(self):
        if not os.path.isdir(EXPORTS_DIR) or not any(x.endswith(".csv") for x in os.listdir(EXPORTS_DIR)):
            raise SystemExit("Aucune donnée à analyser. Lancez d'abord « Récupérer depuis HelloAsso ».")
        cfg = CONFIG_JSON if os.path.isfile(CONFIG_JSON) else None
        foyer_controle.run(EXPORTS_DIR, RESULTS_DIR, self.vars["saison"].get().strip(), cfg)

    def _tout_faire(self):
        self._recuperer()
        self._analyser()

    def _ouvrir_resultats(self):
        if not os.path.isdir(RESULTS_DIR):
            messagebox.showwarning("Résultats", "Aucun résultat pour l'instant. Lancez d'abord l'analyse.")
            return
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", RESULTS_DIR])
            elif os.name == "nt":
                os.startfile(RESULTS_DIR)  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", RESULTS_DIR])
        except Exception as e:
            messagebox.showerror("Ouvrir le dossier", str(e))


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
