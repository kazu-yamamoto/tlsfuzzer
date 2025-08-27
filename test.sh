#! /bin/bash
# ./dist/build/tls-server/tls-server --key=/Users/kazu/http/serverkey.pem --cert=/Users/kazu/http/servercert.pem 127.0.0.1 4433 -v -d
OLDIFS=$IFS
IFS=$'\n'
files=$(cat list.txt)
for i in $files
do
  IFS=$OLDIFS
  echo "$i..."
  if ! eval "PYTHONPATH=. python3 scripts/$i 1> /dev/null 2>&1"; then
    printf '\033[31m%s\033[m\n' 'FAIL!'
    echo "PYTHONPATH=. python3 scripts/$i"
    exit 1
  fi
  echo "$i...done"
  IFS=$'\n'
done
printf '\033[32m%s\033[m\n' 'PASS!'
