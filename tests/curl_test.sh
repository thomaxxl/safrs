#
# Test script covering some simple use cases
#

READER_NAME="TestReader"

echo Get People
curl -X GET --header 'Accept: application/json' --header 'Content-Type: application/vnd.api+json' 'http://127.0.0.1:5000/People/?page[limit]=10&include=books_read%2Cbooks_written%2Creviews&sort=name%2Cemail%2Ccomment%2Cdob' > /dev/null 2>&1

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
 }' 'http://127.0.0.1:5000/People/' 2>/dev/null | jq -r .data.id)

ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo "Get Reader (id $id)"
curl -X GET --header 'Accept: application/json' --header 'Content-Type: application/vnd.api+json' "http://127.0.0.1:5000/People/$id" >/dev/null 2>&1
ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo "Get Readers with filter: http://127.0.0.1:5000/People/?page[limit]=10&include=books_read%2Cbooks_written%2Creviews&sort=name%2Cemail%2Ccomment%2Cdob&filter[name]=$READER_NAME"
curl -g "http://127.0.0.1:5000/People/?page[limit]=10&include=books_read%2Cbooks_written%2Creviews&sort=name%2Cemail%2Ccomment%2Cdob&filter[name]=$READER_NAME" >/dev/null 2>&1

echo Patch Reader
curl -X PATCH --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{  
   "data": {  
     "attributes": {  
       "name": "Reader 0",  
       "email": "reader_email0",  
       "dob" : "1988-08-09",  
       "comment": ""  
     },  
     "id": "5213a17a-b195-4b52-befd-d1c039009517",  
     "type": "People"  
   }  
 }' 'http://127.0.0.1:5000/People/fd220bc4-eb73-4dfe-8cfa-a15f810e88ca/' >/dev/null 2>&1


ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo GET Books
book_id=$(curl -X GET --header 'Accept: application/json' --header 'Content-Type: application/vnd.api+json' 'http://127.0.0.1:5000/Books/?page[limit]=10&include=publisher%2Creviews%2Creader%2Cauthor&sort=title%2Creader_id%2Cauthor_id%2Cpublisher_id' 2>/dev/null | jq -r '.data[0].id')

echo "POST books_read ( reader id : $id, book_id : $book_id)"

curl -X POST --header 'Content-Type: application/json' --header 'Accept: application/json' -d '{  
   "data": [  
     {  
       "type": "Books",
       "attributes": {},  
       "id": "'$book_id'"  
     }  
   ]  
 }' "http://127.0.0.1:5000/People/$id/books_read" >/dev/null 2>&1


ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi


echo GET books_read
books_read_id=$(curl -X GET --header 'Accept: application/json' "http://127.0.0.1:5000/People/$id/books_read?page[limit]=10&include=books_read%2Cbooks_written%2Creviews&sort=name%2Cemail%2Ccomment%2Cdob" 2>/dev/null | jq -r ".data[0].id")

ret=$?
if [[ $ret != 0  || $books_read_id != $book_id ]];then
	echo FAIL
	exit 1
fi

echo "Delete books_read (http://127.0.0.1:5000/People/$id/books_read/$book_id)"
curl -X DELETE --header 'Accept: application/json' "http://127.0.0.1:5000/People/$id/books_read/$book_id" >/dev/null 2>&1

ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi

echo Delete Reader
curl -X DELETE --header 'Accept: application/json' "http://127.0.0.1:5000/People/$id" >/dev/null 2>&1
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
         "type": "string",  
         "example": "test email"  
       }  
     }  
   }  
 }' 'http://127.0.0.1:5000/People/send_mail' > /dev/null 2>&1

ret=$?
if [[ $ret != 0 ]]; then
	echo FAIL
	exit 1
fi



echo DONE