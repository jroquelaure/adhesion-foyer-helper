#!/bin/bash
# Lanceur macOS : trouve Python (par chemin complet, sans dépendre du PATH),
# l'installe automatiquement s'il est absent, puis démarre l'application.
cd "$(dirname "$0")"

PYVER="3.12.7"
PKG_URL="https://www.python.org/ftp/python/${PYVER}/python-${PYVER}-macos11.pkg"

trouver_python() {
  for p in \
    "/opt/homebrew/bin/python3" \
    "/usr/local/bin/python3" \
    /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 \
    "/usr/local/bin/python3.12" \
    "/usr/bin/python3"; do
    if [ -x "$p" ] && "$p" -c 'import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)' 2>/dev/null; then
      echo "$p"; return 0
    fi
  done
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)' 2>/dev/null; then
    command -v python3; return 0
  fi
  return 1
}

PY="$(trouver_python)"

if [ -z "$PY" ]; then
  osascript -e 'display dialog "Python est nécessaire mais n’est pas installé.\n\nCliquez sur Installer pour le télécharger et l’installer automatiquement (votre mot de passe administrateur vous sera demandé)." buttons {"Annuler","Installer"} default button "Installer" with title "Adhésions — installation de Python"' >/dev/null 2>&1
  if [ $? -ne 0 ]; then echo "Installation annulée."; exit 1; fi
  PKG="/tmp/python-foyer-${PYVER}.pkg"
  echo "Téléchargement de Python ${PYVER}…"
  if ! curl -L --fail -o "$PKG" "$PKG_URL"; then
    osascript -e 'display alert "Échec du téléchargement" message "Vérifiez votre connexion Internet, puis relancez. Vous pouvez aussi installer Python manuellement depuis python.org (voir le guide)."'
    exit 1
  fi
  echo "Installation de Python (mot de passe administrateur requis)…"
  if ! osascript -e "do shell script \"installer -pkg '${PKG}' -target /\" with administrator privileges"; then
    osascript -e 'display alert "Échec de l’installation" message "Vous pouvez installer Python manuellement depuis python.org (voir le guide)."'
    exit 1
  fi
  PY="$(trouver_python)"
  if [ -z "$PY" ]; then
    osascript -e 'display alert "Python installé mais introuvable" message "Redémarrez votre Mac puis relancez l’application."'
    exit 1
  fi
fi

# S'assurer que les certificats HTTPS sont disponibles (pour l’API HelloAsso)
"$PY" -c "import certifi" >/dev/null 2>&1 || "$PY" -m pip install --quiet --user certifi >/dev/null 2>&1

echo "Démarrage de l’application…"
exec "$PY" foyer_app.py
