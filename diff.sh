ls -1 scripts > list-all.txt
cat list.txt list-auth.txt | sort | awk '{print $1}' > list-now.txt
diff -u list-all.txt list-now.txt
