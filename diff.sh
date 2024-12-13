ls -1 scripts > list-all.txt
awk '{print $1}' list.txt > list-now.txt
diff -u list-all.txt list-now.txt
