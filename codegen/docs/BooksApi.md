# swagger_client.BooksApi

All URIs are relative to *http://thomaxxl.pythonanywhere.com*

Method | HTTP request | Description
------------- | ------------- | -------------
[**createa_bookobject0**](BooksApi.md#createa_bookobject0) | **POST** /Books/ | Create a Book object            
[**createa_bookobject1**](BooksApi.md#createa_bookobject1) | **POST** /Books/{BookId}/ | Create a Book object                        
[**deletea_bookobject0**](BooksApi.md#deletea_bookobject0) | **DELETE** /Books/{BookId}/ | Delete a Book object            
[**deletefrom_bookuser0**](BooksApi.md#deletefrom_bookuser0) | **DELETE** /Books/{BookId}/user/{UserId} | Delete from Book user
[**invoke_bookgetlist0**](BooksApi.md#invoke_bookgetlist0) | **POST** /Books/get_list | Invoke Book.get_list            
[**retrievea_bookobject0**](BooksApi.md#retrievea_bookobject0) | **GET** /Books/ | Retrieve a Book object            
[**retrievea_bookobject1**](BooksApi.md#retrievea_bookobject1) | **GET** /Books/{BookId}/ | Retrieve a Book object                        
[**retrieveauserobject0**](BooksApi.md#retrieveauserobject0) | **GET** /Books/{BookId}/user | Retrieve a user object
[**retrieveauserobject1**](BooksApi.md#retrieveauserobject1) | **GET** /Books/{BookId}/user/{UserId} | Retrieve a user object
[**updatea_bookobject0**](BooksApi.md#updatea_bookobject0) | **PATCH** /Books/{BookId}/ | Update a Book object            
[**updateuser0**](BooksApi.md#updateuser0) | **POST** /Books/{BookId}/user | Update user


# **createa_bookobject0**
> createa_bookobject0(post_body)

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
    api_instance.createa_bookobject0(post_body)
except ApiException as e:
    print("Exception when calling BooksApi->createa_bookobject0: %s\n" % e)
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

# **createa_bookobject1**
> createa_bookobject1(book_id, post_body)

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
    api_instance.createa_bookobject1(book_id, post_body)
except ApiException as e:
    print("Exception when calling BooksApi->createa_bookobject1: %s\n" % e)
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

# **deletea_bookobject0**
> deletea_bookobject0(book_id)

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
    api_instance.deletea_bookobject0(book_id)
except ApiException as e:
    print("Exception when calling BooksApi->deletea_bookobject0: %s\n" % e)
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

# **deletefrom_bookuser0**
> deletefrom_bookuser0(book_id, user_id)

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
    api_instance.deletefrom_bookuser0(book_id, user_id)
except ApiException as e:
    print("Exception when calling BooksApi->deletefrom_bookuser0: %s\n" % e)
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

# **invoke_bookgetlist0**
> invoke_bookgetlist0(post_book_get_list)

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
    api_instance.invoke_bookgetlist0(post_book_get_list)
except ApiException as e:
    print("Exception when calling BooksApi->invoke_bookgetlist0: %s\n" % e)
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

# **retrievea_bookobject0**
> retrievea_bookobject0(page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)

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
    api_instance.retrievea_bookobject0(page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)
except ApiException as e:
    print("Exception when calling BooksApi->retrievea_bookobject0: %s\n" % e)
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

# **retrievea_bookobject1**
> retrievea_bookobject1(book_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)

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
    api_instance.retrievea_bookobject1(book_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)
except ApiException as e:
    print("Exception when calling BooksApi->retrievea_bookobject1: %s\n" % e)
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

# **retrieveauserobject0**
> retrieveauserobject0(book_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)

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
    api_instance.retrieveauserobject0(book_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_books=fields_books, sort=sort, filter_name=filter_name, filter_user_id=filter_user_id)
except ApiException as e:
    print("Exception when calling BooksApi->retrieveauserobject0: %s\n" % e)
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

# **retrieveauserobject1**
> retrieveauserobject1(book_id, user_id)

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
    api_instance.retrieveauserobject1(book_id, user_id)
except ApiException as e:
    print("Exception when calling BooksApi->retrieveauserobject1: %s\n" % e)
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

# **updatea_bookobject0**
> updatea_bookobject0(book_id, post_body)

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
    api_instance.updatea_bookobject0(book_id, post_body)
except ApiException as e:
    print("Exception when calling BooksApi->updatea_bookobject0: %s\n" % e)
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

# **updateuser0**
> updateuser0(book_id, user_body)

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
    api_instance.updateuser0(book_id, user_body)
except ApiException as e:
    print("Exception when calling BooksApi->updateuser0: %s\n" % e)
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

