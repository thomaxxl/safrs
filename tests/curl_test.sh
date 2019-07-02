#
# Test script covering some simple use cases
#

READER_NAME="TestReader"
HOST=$1
test_host=${HOST:="http://127.0.0.1:5000"}

echo Get People
curl -X GET --header 'Accept: application/json' --header 'Content-Type: application/vnd.api+json' "$test_host"'/People/?page[limit]=10&include=books_read%2Cbooks_written%2Creviews&sort=name%2Cemail%2Ccomment%2Cdob' > /dev/null 2>&1

ret=$?

if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo Create Reader
id=$(curl -X POST --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{  
   "data": {  
     "attributes": {  
       "name": "'$READER_NAME'",  
 	   "dob": "1970-01-09",  
       "email": "reader_email0",  
       "comment": ""  
     },  
     "type": "People"  
   }  
 }' "$test_host/People/" 2>/dev/null | jq -r .data.id)

ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo "Get Reader (id $id)"
curl -X GET --header 'Accept: application/json' --header 'Content-Type: application/vnd.api+json' "$test_host/People/$id" >/dev/null 2>&1
ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo "Get Readers with filter: $test_host/People/?page[limit]=10&include=books_read%2Cbooks_written%2Creviews&sort=name%2Cemail%2Ccomment%2Cdob&filter[name]=$READER_NAME"
curl -g "$test_host/People/?page[limit]=10&include=books_read%2Cbooks_written%2Creviews&sort=name%2Cemail%2Ccomment%2Cdob&filter[name]=$READER_NAME" >/dev/null 2>&1

echo Patch Reader
curl -X PATCH --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{  
   "data": {  
     "attributes": {  
       "name": "Reader 0",  
       "email": "reader_email0",  
       "dob" : "1988-08-09",  
       "comment": ""  
     },  
     "id": "'$id'",  
     "type": "People"  
   }  
 }' "$test_host/People/$id/" >/dev/null 2>&1


ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo GET Books
book_id=$(curl -X GET --header 'Accept: application/json' --header 'Content-Type: application/vnd.api+json' "$test_host"'/Books/?page[limit]=10&include=publisher%2Creviews%2Creader%2Cauthor&sort=title%2Creader_id%2Cauthor_id%2Cpublisher_id' 2>/dev/null | jq -r '.data[0].id')

echo "POST books_read ( reader id : $id, book_id : $book_id)"

curl -X POST --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{  
   "data": [  
     {  
       "type": "Books",
       "attributes": {},  
       "id": "'$book_id'"  
     }  
   ]  
 }' "$test_host/People/$id/books_read" >/dev/null 2>&1


ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi


echo GET books_read
books_read_id=$(curl -X GET --header 'Accept: application/json' "$test_host/People/$id"'/books_read?page[limit]=10&include=publisher&sort=title' 2>/dev/null | jq -r ".data[0].id")

ret=$?
if [[ $ret != 0  || $books_read_id != $book_id ]];then
	echo FAIL
	exit 1
fi

echo "Delete books_read ($test_host/People/$id/books_read/$book_id)"
curl -X DELETE --header 'Accept: application/json' "$test_host/People/$id/books_read/$book_id" >/dev/null 2>&1

ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo Delete Reader
curl -X DELETE --header 'Accept: application/json' "$test_host/People/$id" >/dev/null 2>&1
ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo "Test Filter"
filter_count=$(curl -X GET --header 'Accept: application/json' --header 'Content-Type: application/vnd.api+json' "$test_host"'/People/?page%5Boffset%5D=0&page%5Blimit%5D=10&include=books_read%2Cbooks_written%2Creviews&fields%5BPeople%5D=name%2Cemail%2Ccomment%2Cdob&sort=name%2Cemail%2Ccomment%2Cdob&filter%5Bname%5D=Author%200%2CAuthor%201&filter%5Bemail%5D=author_email0%2Cauthor_email1'  2>/dev/null | jq -r ".meta.count")
ret=$?
if [[ $ret != 0 || $filter_count != 2 ]]; then
  echo FAIL
  exit 1
fi


curl -X GET --header 'Accept: application/json' --header 'Content-Type: application/vnd.api+json' "$test_host"'/People/?page[limit]=10&sort=name%2Cemail%2Ccomment%2Cdob&filter[name]=Author%200&fields[People]=name,dob' >/dev/null 2>&1
ret=$?
if [[ $ret != 0 ]]; then
  echo FAIL
  exit 1
fi

echo Send Mail
curl -X POST --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{  
   "meta": {  
     "method": "send_mail",  
     "args": {  
       "email": {  
         "example": "test email"  
       }  
     }  
   }  
 }' "$test_host/People/$id/send_mail" > /dev/null 2>&1

ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo Test my_rpc
curl -X GET "$test_host/People/my_rpc?my_query_string_param=my_value&my_post_body_param=xxx" -H "accept: application/json" > /dev/null 2>&1

ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

curl -X GET "$test_host/People/?page%5Boffset%5D=0&page%5Blimit%5D=10&include=books_read%2Cbooks_written%2Creviews&fields%5BPeople%5D=name%2Cemail%2Ccomment%2Cdob&sort=name%2Cemail%2Ccomment%2Cdob&filter%5Bname%5D=xxx" -H "accept: application/json" -H "Content-Type: application/vnd.api+json" > /dev/null 2>&1

ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

curl -X GET "$test_host/People/?page%5Boffset%5D=0&page%5Blimit%5D=10&include=books_read%2Cbooks_written%2Creviews&fields%5BPeople%5D=name%2Cemail%2Ccomment%2Cdob&sort=name%2Cemail%2Ccomment%2Cdob&filter%5Bname%5D=xxx&filter%5Bdob%5D=x" -H "accept: application/json" -H "Content-Type: application/vnd.api+json" > /dev/null 2>&1

ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo "Test Publisher/books count"
pub_book_count=$(curl -X GET  "$test_host/Publishers/1/?page%5Boffset%5D=0&page%5Blimit%5D=10&include=books&fields%5BPublishers%5D=name&sort=name" -H "accept: application/json" -H "Content-Type: application/vnd.api+json" 2>/dev/null| jq -r .meta.count)
ret=$?
if [[ $pub_book_count != 1 || $ret != 0 ]]; then
  echo FAIL
  exit 1
fi
 
#curl $test_host/sd

echo DONE
