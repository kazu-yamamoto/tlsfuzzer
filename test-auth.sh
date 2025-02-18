# ./dist/build/tls-server/tls-server --key=/Users/kazu/http/serverkey.pem --cert=/Users/kazu/http/servercert.pem 127.0.0.1 4433 -v -d -a -t /Users/kazu/http/cacert.pem
OLDIFS=$IFS
IFS=$'\n'
files=`cat list-auth.txt`
for i in $files
do
  IFS=$OLDIFS
  echo "$i..."
  eval "PYTHONPATH=. python3 scripts/$i -k ~/http/clientkey.pem -c ~/http/clientcert.pem 1> /dev/null 2>&1"
  r=$?
  if [ $r -ne 0 ]; then
    echo "FAIL!"
    echo "PYTHONPATH=. python3 scripts/$i -k ~/http/clientkey.pem -c ~/http/clientcert.pem"
    exit 1
  fi
  echo "$i...done"
  IFS=$'\n'
done
echo "PASS"
