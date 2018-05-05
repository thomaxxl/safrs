# swagger_client.BooksApi

All URIs are relative to *https://localhost:5000*

Method | HTTP request | Description
------------- | ------------- | -------------
[**delete_booksstring_book_id_ad0d**](BooksApi.md#delete_booksstring_book_id_ad0d) | **DELETE** /Books/{BookId}/ | Delete a Book object            
[**delete_booksstring_book_id_userstring_user_id25ae**](BooksApi.md#delete_booksstring_book_id_userstring_user_id25ae) | **DELETE** /Books/{BookId}/user/{UserId} | Delete from Book user
[**get_books49c2**](BooksApi.md#get_books49c2) | **GET** /Books/ | Retrieve a Book object            
[**get_booksstring_book_id5596**](BooksApi.md#get_booksstring_book_id5596) | **GET** /Books/{BookId}/ | Retrieve a Book object                        
[**get_booksstring_book_id_userfe6e**](BooksApi.md#get_booksstring_book_id_userfe6e) | **GET** /Books/{BookId}/user | Retrieve a user object
[**get_booksstring_book_id_userstring_user_idecbd**](BooksApi.md#get_booksstring_book_id_userstring_user_idecbd) | **GET** /Books/{BookId}/user/{UserId} | Retrieve a user object
[**patch_booksstring_book_id_b128**](BooksApi.md#patch_booksstring_book_id_b128) | **PATCH** /Books/{BookId}/ | Update a Book object            
[**post_books_dbb6**](BooksApi.md#post_books_dbb6) | **POST** /Books/ | Create a Book object            
[**post_books_get_list7301**](BooksApi.md#post_books_get_list7301) | **POST** /Books/get_list | Invoke Book.get_list            
[**post_books_lookup0981**](BooksApi.md#post_books_lookup0981) | **POST** /Books/lookup | Invoke Book.lookup            
[**post_booksstring_book_id1dee**](BooksApi.md#post_booksstring_book_id1dee) | **POST** /Books/{BookId}/ | Create a Book object                        
[**post_booksstring_book_id_user0e8a**](BooksApi.md#post_booksstring_book_id_user0e8a) | **POST** /Books/{BookId}/user | Update user


# **delete_booksstring_book_id_ad0d**
> delete_booksstring_book_id_ad0d(book_id)

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
    api_instance.delete_booksstring_book_id_ad0d(book_id)
except ApiException as e:
    print("Exception when calling BooksApi->delete_booksstring_book_id_ad0d: %s\n" % e)
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

# **delete_booksstring_book_id_userstring_user_id25ae**
> delete_booksstring_book_id_userstring_user_id25ae(book_id, user_id)

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
    api_instance.delete_booksstring_book_id_userstring_user_id25ae(book_id, user_id)
except ApiException as e:
    print("Exception when calling BooksApi->delete_booksstring_book_id_userstring_user_id25ae: %s\n" % e)
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

# **get_books49c2**
> get_books49c2(page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_book_id=fields_book_id)

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
sort = '' # str | sort fields (optional) (default to )
fields_book_id = '' # str | fields (optional) (default to )

try:
    # Retrieve a Book object            
    api_instance.get_books49c2(page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_book_id=fields_book_id)
except ApiException as e:
    print("Exception when calling BooksApi->get_books49c2: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **sort** | **str**| sort fields | [optional] [default to ]
 **fields_book_id** | **str**| fields | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_booksstring_book_id5596**
> get_booksstring_book_id5596(book_id, page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_book_id=fields_book_id)

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
sort = '' # str | sort fields (optional) (default to )
fields_book_id = '' # str | fields (optional) (default to )

try:
    # Retrieve a Book object                        
    api_instance.get_booksstring_book_id5596(book_id, page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_book_id=fields_book_id)
except ApiException as e:
    print("Exception when calling BooksApi->get_booksstring_book_id5596: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **book_id** | **str**|  | 
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **sort** | **str**| sort fields | [optional] [default to ]
 **fields_book_id** | **str**| fields | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_booksstring_book_id_userfe6e**
> get_booksstring_book_id_userfe6e(book_id, page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_book_id=fields_book_id, fields_user_id=fields_user_id)

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
sort = '' # str | sort fields (optional) (default to )
fields_book_id = '' # str | fields (optional) (default to )
fields_user_id = '' # str | fields (optional) (default to )

try:
    # Retrieve a user object
    api_instance.get_booksstring_book_id_userfe6e(book_id, page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_book_id=fields_book_id, fields_user_id=fields_user_id)
except ApiException as e:
    print("Exception when calling BooksApi->get_booksstring_book_id_userfe6e: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **book_id** | **str**| Book item | 
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **sort** | **str**| sort fields | [optional] [default to ]
 **fields_book_id** | **str**| fields | [optional] [default to ]
 **fields_user_id** | **str**| fields | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_booksstring_book_id_userstring_user_idecbd**
> get_booksstring_book_id_userstring_user_idecbd(book_id, user_id)

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
    api_instance.get_booksstring_book_id_userstring_user_idecbd(book_id, user_id)
except ApiException as e:
    print("Exception when calling BooksApi->get_booksstring_book_id_userstring_user_idecbd: %s\n" % e)
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

# **patch_booksstring_book_id_b128**
> patch_booksstring_book_id_b128(book_id, post_body)

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
    api_instance.patch_booksstring_book_id_b128(book_id, post_body)
except ApiException as e:
    print("Exception when calling BooksApi->patch_booksstring_book_id_b128: %s\n" % e)
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

# **post_books_dbb6**
> post_books_dbb6(post_body)

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
    api_instance.post_books_dbb6(post_body)
except ApiException as e:
    print("Exception when calling BooksApi->post_books_dbb6: %s\n" % e)
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

# **post_books_get_list7301**
> post_books_get_list7301(post_book_get_list)

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
    api_instance.post_books_get_list7301(post_book_get_list)
except ApiException as e:
    print("Exception when calling BooksApi->post_books_get_list7301: %s\n" % e)
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

# **post_books_lookup0981**
> post_books_lookup0981(post_book_lookup)

Invoke Book.lookup            

Invoke Book.lookup

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.BooksApi()
post_book_lookup = swagger_client.PostBookLookup() # PostBookLookup | Retrieve all matching objects

try:
    # Invoke Book.lookup            
    api_instance.post_books_lookup0981(post_book_lookup)
except ApiException as e:
    print("Exception when calling BooksApi->post_books_lookup0981: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **post_book_lookup** | [**PostBookLookup**](PostBookLookup.md)| Retrieve all matching objects | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **post_booksstring_book_id1dee**
> post_booksstring_book_id1dee(book_id, post_body)

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
    api_instance.post_booksstring_book_id1dee(book_id, post_body)
except ApiException as e:
    print("Exception when calling BooksApi->post_booksstring_book_id1dee: %s\n" % e)
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

# **post_booksstring_book_id_user0e8a**
> post_booksstring_book_id_user0e8a(book_id, user_body)

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
    api_instance.post_booksstring_book_id_user0e8a(book_id, user_body)
except ApiException as e:
    print("Exception when calling BooksApi->post_booksstring_book_id_user0e8a: %s\n" % e)
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

