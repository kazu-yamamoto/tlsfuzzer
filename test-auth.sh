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
    echo "PYTHONPATH=. python3 scripts/$i"
    exit 1
  fi
  echo "$i...done"
  IFS=$'\n'
done
echo "PASS"
