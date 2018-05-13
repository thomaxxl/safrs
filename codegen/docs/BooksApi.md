# swagger_client.BooksApi

All URIs are relative to *http://thomaxxl.pythonanywhere.com*

Method | HTTP request | Description
------------- | ------------- | -------------
[**oid2**](BooksApi.md#oid2) | **PATCH** /Books/{BookId}/ | Update a Book object            
[**oid3**](BooksApi.md#oid3) | **DELETE** /Books/{BookId}/ | Delete a Book object            
[**oid4**](BooksApi.md#oid4) | **DELETE** /Books/{BookId}/user/{UserId} | Delete from Book user
[**oid5**](BooksApi.md#oid5) | **GET** /Books/ | Retrieve a Book object            
[**oid5_0**](BooksApi.md#oid5_0) | **POST** /Books/ | Create a Book object            
[**oid6**](BooksApi.md#oid6) | **GET** /Books/{BookId}/ | Retrieve a Book object                        
[**oid6_0**](BooksApi.md#oid6_0) | **POST** /Books/{BookId}/ | Create a Book object                        
[**oid7**](BooksApi.md#oid7) | **GET** /Books/{BookId}/user | Retrieve a user object
[**oid7_0**](BooksApi.md#oid7_0) | **POST** /Books/{BookId}/user | Update user
[**oid8**](BooksApi.md#oid8) | **POST** /Books/get_list | Invoke Book.get_list            
[**oid8_0**](BooksApi.md#oid8_0) | **GET** /Books/{BookId}/user/{UserId} | Retrieve a user object


# **oid2**
> oid2(book_id, post_body)

Update a Book object            

Returns a Book

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
book_id = 'book_id_example' # str | 
post_body = swagger_client.BookPOSTSample1() # BookPOSTSample1 | Book attributes

try:
    # Update a Book object            
    api_instance.oid2(book_id, post_body)
except ApiException as e:
    print("Exception when calling BooksApi->oid2: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **book_id** | **str**|  | 
 **post_body** | [**BookPOSTSample1**](BookPOSTSample1.md)| Book attributes | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **oid3**
> oid3(book_id)

Delete a Book object            

Delete a Book object

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
book_id = 'book_id_example' # str | 

try:
    # Delete a Book object            
    api_instance.oid3(book_id)
except ApiException as e:
    print("Exception when calling BooksApi->oid3: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **book_id** | **str**|  | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **oid4**
> oid4(book_id, user_id)

Delete from Book user

Delete a User object from the user relation on Book

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
book_id = 'book_id_example' # str | Book item
user_id = 'user_id_example' # str | user item

try:
    # Delete from Book user
    api_instance.oid4(book_id, user_id)
except ApiException as e:
    print("Exception when calling BooksApi->oid4: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **book_id** | **str**| Book item | 
 **user_id** | **str**| user item | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **oid5**
> oid5(page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)

Retrieve a Book object            

Returns a Book

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
page_offset = 0 # int | Page offset (optional) (default to 0)
page_limit = 10 # int | max number of items (optional) (default to 10)
include = '' # str | related objects to include (optional) (default to )
fields_books = '' # str | Fields to be selected (csv) (optional) (default to )
sort = 'id,name,user_id' # str | Sort order (optional) (default to id,name,user_id)
filter_name = '' # str | name attribute filter (csv) (optional) (default to )
filter_user_id = '' # str | user_id attribute filter (csv) (optional) (default to )

try:
    # Retrieve a Book object            
    api_instance.oid5(page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)
except ApiException as e:
    print("Exception when calling BooksApi->oid5: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **fields_books** | **str**| Fields to be selected (csv) | [optional] [default to ]
 **sort** | **str**| Sort order | [optional] [default to id,name,user_id]
 **filter_name** | **str**| name attribute filter (csv) | [optional] [default to ]
 **filter_user_id** | **str**| user_id attribute filter (csv) | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **oid5_0**
> oid5_0(post_body)

Create a Book object            

Returns a Book

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
post_body = swagger_client.BookPOSTSample() # BookPOSTSample | Book attributes

try:
    # Create a Book object            
    api_instance.oid5_0(post_body)
except ApiException as e:
    print("Exception when calling BooksApi->oid5_0: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **post_body** | [**BookPOSTSample**](BookPOSTSample.md)| Book attributes | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **oid6**
> oid6(book_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)

Retrieve a Book object                        

Returns a Book

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
book_id = 'book_id_example' # str | 
page_offset = 0 # int | Page offset (optional) (default to 0)
page_limit = 10 # int | max number of items (optional) (default to 10)
include = '' # str | related objects to include (optional) (default to )
fields_books = '' # str | Fields to be selected (csv) (optional) (default to )
sort = 'id,name,user_id' # str | Sort order (optional) (default to id,name,user_id)
filter_name = '' # str | name attribute filter (csv) (optional) (default to )
filter_user_id = '' # str | user_id attribute filter (csv) (optional) (default to )

try:
    # Retrieve a Book object                        
    api_instance.oid6(book_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)
except ApiException as e:
    print("Exception when calling BooksApi->oid6: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **book_id** | **str**|  | 
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **fields_books** | **str**| Fields to be selected (csv) | [optional] [default to ]
 **sort** | **str**| Sort order | [optional] [default to id,name,user_id]
 **filter_name** | **str**| name attribute filter (csv) | [optional] [default to ]
 **filter_user_id** | **str**| user_id attribute filter (csv) | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **oid6_0**
> oid6_0(book_id, post_body)

Create a Book object                        

Returns a Book

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
book_id = 'book_id_example' # str | 
post_body = swagger_client.BookPOSTSample() # BookPOSTSample | Book attributes

try:
    # Create a Book object                        
    api_instance.oid6_0(book_id, post_body)
except ApiException as e:
    print("Exception when calling BooksApi->oid6_0: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **book_id** | **str**|  | 
 **post_body** | [**BookPOSTSample**](BookPOSTSample.md)| Book attributes | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **oid7**
> oid7(book_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)

Retrieve a user object

Returns Book user ids

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
book_id = 'book_id_example' # str | Book item
page_offset = 0 # int | Page offset (optional) (default to 0)
page_limit = 10 # int | max number of items (optional) (default to 10)
include = '' # str | related objects to include (optional) (default to )
fields_books = '' # str | Fields to be selected (csv) (optional) (default to )
sort = 'id,name,user_id' # str | Sort order (optional) (default to id,name,user_id)
filter_name = '' # str | name attribute filter (csv) (optional) (default to )
filter_user_id = '' # str | user_id attribute filter (csv) (optional) (default to )

try:
    # Retrieve a user object
    api_instance.oid7(book_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)
except ApiException as e:
    print("Exception when calling BooksApi->oid7: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **book_id** | **str**| Book item | 
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **fields_books** | **str**| Fields to be selected (csv) | [optional] [default to ]
 **sort** | **str**| Sort order | [optional] [default to id,name,user_id]
 **filter_name** | **str**| name attribute filter (csv) | [optional] [default to ]
 **filter_user_id** | **str**| user_id attribute filter (csv) | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **oid7_0**
> oid7_0(book_id, user_body)

Update user

Add a User object to the user relation on Book

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
book_id = 'book_id_example' # str | Book item
user_body = swagger_client.UserRelationship() # UserRelationship | user POST model

try:
    # Update user
    api_instance.oid7_0(book_id, user_body)
except ApiException as e:
    print("Exception when calling BooksApi->oid7_0: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **book_id** | **str**| Book item | 
 **user_body** | [**UserRelationship**](UserRelationship.md)| user POST model | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **oid8**
> oid8(post_book_get_list)

Invoke Book.get_list            

Invoke Book.get_list

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
post_book_get_list = swagger_client.PostBookGetList() # PostBookGetList | Retrieve a list of objects with the ids in id_list.

try:
    # Invoke Book.get_list            
    api_instance.oid8(post_book_get_list)
except ApiException as e:
    print("Exception when calling BooksApi->oid8: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **post_book_get_list** | [**PostBookGetList**](PostBookGetList.md)| Retrieve a list of objects with the ids in id_list. | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **oid8_0**
> oid8_0(book_id, user_id)

Retrieve a user object

Returns Book user ids

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
book_id = 'book_id_example' # str | Book item
user_id = 'user_id_example' # str | user item

try:
    # Retrieve a user object
    api_instance.oid8_0(book_id, user_id)
except ApiException as e:
    print("Exception when calling BooksApi->oid8_0: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **book_id** | **str**| Book item | 
 **user_id** | **str**| user item | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

