#!/usr/bin/env bash
# Usage: ./push_update.sh            (uses the default message)
#        ./push_update.sh "my message"
set -e
MSG="${1:-Add orders database, Case Detective, action verification and smart handover}"
git add -A
git commit -m "$MSG" || echo "Nothing new to commit."
git push
echo "Pushed. Render will redeploy automatically."
