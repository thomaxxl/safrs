# swagger_client.UsersApi

All URIs are relative to *https://localhost:5000*

Method | HTTP request | Description
------------- | ------------- | -------------
[**delete_usersstring_user_id2665**](UsersApi.md#delete_usersstring_user_id2665) | **DELETE** /Users/{UserId}/ | Delete a User object            
[**delete_usersstring_user_id_booksstring_book_id24aa**](UsersApi.md#delete_usersstring_user_id_booksstring_book_id24aa) | **DELETE** /Users/{UserId}/books/{BookId} | Delete from User books
[**get_users_b2b8**](UsersApi.md#get_users_b2b8) | **GET** /Users/ | Retrieve a User object            
[**get_usersstring_user_id_books8b31**](UsersApi.md#get_usersstring_user_id_books8b31) | **GET** /Users/{UserId}/books | Retrieve a books object
[**get_usersstring_user_id_booksstring_book_id9c49**](UsersApi.md#get_usersstring_user_id_booksstring_book_id9c49) | **GET** /Users/{UserId}/books/{BookId} | Retrieve a books object
[**get_usersstring_user_id_c5e7**](UsersApi.md#get_usersstring_user_id_c5e7) | **GET** /Users/{UserId}/ | Retrieve a User object                        
[**patch_usersstring_user_id_c1d3**](UsersApi.md#patch_usersstring_user_id_c1d3) | **PATCH** /Users/{UserId}/ | Update a User object            
[**post_users1c2c**](UsersApi.md#post_users1c2c) | **POST** /Users/ | Create a User object            
[**post_users_get_list3413**](UsersApi.md#post_users_get_list3413) | **POST** /Users/get_list | Invoke User.get_list            
[**post_users_lookupd016**](UsersApi.md#post_users_lookupd016) | **POST** /Users/lookup | Invoke User.lookup            
[**post_usersstring_user_id_books0a50**](UsersApi.md#post_usersstring_user_id_books0a50) | **POST** /Users/{UserId}/books | Update books
[**post_usersstring_user_id_cd56**](UsersApi.md#post_usersstring_user_id_cd56) | **POST** /Users/{UserId}/ | Create a User object                        
[**post_usersstring_user_id_send_mail5969**](UsersApi.md#post_usersstring_user_id_send_mail5969) | **POST** /Users/{UserId}/send_mail | Invoke User.send_mail            


# **delete_usersstring_user_id2665**
> delete_usersstring_user_id2665(user_id)

Delete a User object            

Delete a User object

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
user_id = 'user_id_example' # str | 

try:
    # Delete a User object            
    api_instance.delete_usersstring_user_id2665(user_id)
except ApiException as e:
    print("Exception when calling UsersApi->delete_usersstring_user_id2665: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**|  | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_usersstring_user_id_booksstring_book_id24aa**
> delete_usersstring_user_id_booksstring_book_id24aa(user_id, book_id)

Delete from User books

Delete a Book object from the books relation on User

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
user_id = 'user_id_example' # str | User item
book_id = 'book_id_example' # str | books item

try:
    # Delete from User books
    api_instance.delete_usersstring_user_id_booksstring_book_id24aa(user_id, book_id)
except ApiException as e:
    print("Exception when calling UsersApi->delete_usersstring_user_id_booksstring_book_id24aa: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**| User item | 
 **book_id** | **str**| books item | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_users_b2b8**
> get_users_b2b8(page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_user_id=fields_user_id)

Retrieve a User object            

Returns a User

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
page_offset = 0 # int | Page offset (optional) (default to 0)
page_limit = 10 # int | max number of items (optional) (default to 10)
include = '' # str | related objects to include (optional) (default to )
sort = '' # str | sort fields (optional) (default to )
fields_user_id = '' # str | fields (optional) (default to )

try:
    # Retrieve a User object            
    api_instance.get_users_b2b8(page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_user_id=fields_user_id)
except ApiException as e:
    print("Exception when calling UsersApi->get_users_b2b8: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **sort** | **str**| sort fields | [optional] [default to ]
 **fields_user_id** | **str**| fields | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_usersstring_user_id_books8b31**
> get_usersstring_user_id_books8b31(user_id, page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_user_id=fields_user_id, fields_book_id=fields_book_id)

Retrieve a books object

Returns User books ids

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
user_id = 'user_id_example' # str | User item
page_offset = 0 # int | Page offset (optional) (default to 0)
page_limit = 10 # int | max number of items (optional) (default to 10)
include = '' # str | related objects to include (optional) (default to )
sort = '' # str | sort fields (optional) (default to )
fields_user_id = '' # str | fields (optional) (default to )
fields_book_id = '' # str | fields (optional) (default to )

try:
    # Retrieve a books object
    api_instance.get_usersstring_user_id_books8b31(user_id, page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_user_id=fields_user_id, fields_book_id=fields_book_id)
except ApiException as e:
    print("Exception when calling UsersApi->get_usersstring_user_id_books8b31: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**| User item | 
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **sort** | **str**| sort fields | [optional] [default to ]
 **fields_user_id** | **str**| fields | [optional] [default to ]
 **fields_book_id** | **str**| fields | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_usersstring_user_id_booksstring_book_id9c49**
> get_usersstring_user_id_booksstring_book_id9c49(user_id, book_id)

Retrieve a books object

Returns User books ids

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
user_id = 'user_id_example' # str | User item
book_id = 'book_id_example' # str | books item

try:
    # Retrieve a books object
    api_instance.get_usersstring_user_id_booksstring_book_id9c49(user_id, book_id)
except ApiException as e:
    print("Exception when calling UsersApi->get_usersstring_user_id_booksstring_book_id9c49: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**| User item | 
 **book_id** | **str**| books item | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_usersstring_user_id_c5e7**
> get_usersstring_user_id_c5e7(user_id, page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_user_id=fields_user_id)

Retrieve a User object                        

Returns a User

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
user_id = 'user_id_example' # str | 
page_offset = 0 # int | Page offset (optional) (default to 0)
page_limit = 10 # int | max number of items (optional) (default to 10)
include = '' # str | related objects to include (optional) (default to )
sort = '' # str | sort fields (optional) (default to )
fields_user_id = '' # str | fields (optional) (default to )

try:
    # Retrieve a User object                        
    api_instance.get_usersstring_user_id_c5e7(user_id, page_offset=page_offset, page_limit=page_limit, include=include, sort=sort, fields_user_id=fields_user_id)
except ApiException as e:
    print("Exception when calling UsersApi->get_usersstring_user_id_c5e7: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**|  | 
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **sort** | **str**| sort fields | [optional] [default to ]
 **fields_user_id** | **str**| fields | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **patch_usersstring_user_id_c1d3**
> patch_usersstring_user_id_c1d3(user_id, post_body)

Update a User object            

Returns a User

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
user_id = 'user_id_example' # str | 
post_body = swagger_client.UserPOSTSample1() # UserPOSTSample1 | User attributes

try:
    # Update a User object            
    api_instance.patch_usersstring_user_id_c1d3(user_id, post_body)
except ApiException as e:
    print("Exception when calling UsersApi->patch_usersstring_user_id_c1d3: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**|  | 
 **post_body** | [**UserPOSTSample1**](UserPOSTSample1.md)| User attributes | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **post_users1c2c**
> post_users1c2c(post_body)

Create a User object            

Returns a User

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
post_body = swagger_client.UserPOSTSample() # UserPOSTSample | User attributes

try:
    # Create a User object            
    api_instance.post_users1c2c(post_body)
except ApiException as e:
    print("Exception when calling UsersApi->post_users1c2c: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **post_body** | [**UserPOSTSample**](UserPOSTSample.md)| User attributes | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **post_users_get_list3413**
> post_users_get_list3413(post_user_get_list)

Invoke User.get_list            

Invoke User.get_list

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
post_user_get_list = swagger_client.PostUserGetList() # PostUserGetList | Retrieve a list of objects with the ids in id_list.

try:
    # Invoke User.get_list            
    api_instance.post_users_get_list3413(post_user_get_list)
except ApiException as e:
    print("Exception when calling UsersApi->post_users_get_list3413: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **post_user_get_list** | [**PostUserGetList**](PostUserGetList.md)| Retrieve a list of objects with the ids in id_list. | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **post_users_lookupd016**
> post_users_lookupd016(post_user_lookup)

Invoke User.lookup            

Invoke User.lookup

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
post_user_lookup = swagger_client.PostUserLookup() # PostUserLookup | Retrieve all matching objects

try:
    # Invoke User.lookup            
    api_instance.post_users_lookupd016(post_user_lookup)
except ApiException as e:
    print("Exception when calling UsersApi->post_users_lookupd016: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **post_user_lookup** | [**PostUserLookup**](PostUserLookup.md)| Retrieve all matching objects | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **post_usersstring_user_id_books0a50**
> post_usersstring_user_id_books0a50(user_id, books_body)

Update books

Add a Book object to the books relation on User

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
user_id = 'user_id_example' # str | User item
books_body = swagger_client.BooksRelationship() # BooksRelationship | books POST model

try:
    # Update books
    api_instance.post_usersstring_user_id_books0a50(user_id, books_body)
except ApiException as e:
    print("Exception when calling UsersApi->post_usersstring_user_id_books0a50: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**| User item | 
 **books_body** | [**BooksRelationship**](BooksRelationship.md)| books POST model | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **post_usersstring_user_id_cd56**
> post_usersstring_user_id_cd56(user_id, post_body)

Create a User object                        

Returns a User

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
user_id = 'user_id_example' # str | 
post_body = swagger_client.UserPOSTSample() # UserPOSTSample | User attributes

try:
    # Create a User object                        
    api_instance.post_usersstring_user_id_cd56(user_id, post_body)
except ApiException as e:
    print("Exception when calling UsersApi->post_usersstring_user_id_cd56: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**|  | 
 **post_body** | [**UserPOSTSample**](UserPOSTSample.md)| User attributes | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **post_usersstring_user_id_send_mail5969**
> post_usersstring_user_id_send_mail5969(post_user_send_mail, user_id)

Invoke User.send_mail            

Invoke User.send_mail

### Example
```python
from __future__ import print_function
import time
import swagger_client
from swagger_client.rest import ApiException
from pprint import pprint

# create an instance of the API class
api_instance = swagger_client.UsersApi()
post_user_send_mail = swagger_client.PostUserSendMail() # PostUserSendMail | Send an email
user_id = 'user_id_example' # str | 

try:
    # Invoke User.send_mail            
    api_instance.post_usersstring_user_id_send_mail5969(post_user_send_mail, user_id)
except ApiException as e:
    print("Exception when calling UsersApi->post_usersstring_user_id_send_mail5969: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **post_user_send_mail** | [**PostUserSendMail**](PostUserSendMail.md)| Send an email | 
 **user_id** | **str**|  | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

