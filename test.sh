#! /bin/bash
# ./dist/build/tls-server/tls-server --key=/Users/kazu/http/serverkey.pem --cert=/Users/kazu/http/servercert.pem 127.0.0.1 4433 -v -d --use-weak-ciphers
#
# Environment variables:
#   TLS_HOST  host of tls-server (default: localhost)
#   TLS_PORT  port of tls-server (default: 4433)
#   PYTHON    python interpreter (default: python3)
#   LIST      list of scripts (default: list.txt).  list-ecdsa.txt and
#             list-eddsa.txt are for tls-server given an ECDSA and an
#             Ed25519 certificate.
TLS_HOST=${TLS_HOST:-localhost}
TLS_PORT=${TLS_PORT:-4433}
PYTHON=${PYTHON:-python3}
LIST=${LIST:-list.txt}
out=$(mktemp)
trap 'rm -f "$out"' EXIT
OLDIFS=$IFS
IFS=$'\n'
files=$(cat "$LIST")
for i in $files
do
  IFS=$OLDIFS
  echo "$i..."
  cmd="PYTHONPATH=. $PYTHON scripts/$i -h $TLS_HOST -p $TLS_PORT"
  if ! eval "$cmd" > "$out" 2>&1; then
    cat "$out"
    printf '\033[31m%s\033[m\n' 'FAIL!'
    echo "$cmd"
    exit 1
  fi
  echo "$i...done"
  IFS=$'\n'
done
printf '\033[32m%s\033[m\n' 'PASS!'
