#! /bin/bash
# ./dist/build/tls-server/tls-server --key=/Users/kazu/http/serverkey.pem --cert=/Users/kazu/http/servercert.pem 127.0.0.1 4433 -v -d --use-weak-ciphers -a -t /Users/kazu/http/cacert.pem
#
# Environment variables:
#   TLS_HOST  host of tls-server (default: localhost)
#   TLS_PORT  port of tls-server (default: 4433)
#   PYTHON    python interpreter (default: python3)
#   CERT_DIR  directory of clientkey.pem and clientcert.pem (default: ~/http)
#   CLIENT_KEY, CLIENT_CERT
#             client key and certificate (default: clientkey.pem and
#             clientcert.pem in CERT_DIR)
#   LIST      list of scripts (default: list-auth.txt).  list-auth2.txt is
#             for post-handshake authentication, with tls-server given -t
#             but not -a.
TLS_HOST=${TLS_HOST:-localhost}
TLS_PORT=${TLS_PORT:-4433}
PYTHON=${PYTHON:-python3}
CERT_DIR=${CERT_DIR:-~/http}
CLIENT_KEY=${CLIENT_KEY:-$CERT_DIR/clientkey.pem}
CLIENT_CERT=${CLIENT_CERT:-$CERT_DIR/clientcert.pem}
LIST=${LIST:-list-auth.txt}
out=$(mktemp)
trap 'rm -f "$out"' EXIT
OLDIFS=$IFS
IFS=$'\n'
files=$(cat "$LIST")
for i in $files
do
  IFS=$OLDIFS
  echo "$i..."
  cmd="PYTHONPATH=. $PYTHON scripts/$i -k $CLIENT_KEY -c $CLIENT_CERT -h $TLS_HOST -p $TLS_PORT"
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
