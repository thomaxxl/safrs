# swagger_client.UsersApi

All URIs are relative to *http://thomaxxl.pythonanywhere.com*

Method | HTTP request | Description
------------- | ------------- | -------------
[**1**](UsersApi.md#1) | **GET** /Users/ | Retrieve a User object            
[**1_0**](UsersApi.md#1_0) | **POST** /Users/ | Create a User object            
[**1_1**](UsersApi.md#1_1) | **DELETE** /Users/{UserId}/ | Delete a User object            
[**1_2**](UsersApi.md#1_2) | **PATCH** /Users/{UserId}/ | Update a User object            
[**2**](UsersApi.md#2) | **GET** /Users/{UserId}/ | Retrieve a User object                        
[**2_0**](UsersApi.md#2_0) | **POST** /Users/{UserId}/ | Create a User object                        
[**2_1**](UsersApi.md#2_1) | **DELETE** /Users/{UserId}/books/{BookId} | Delete from User books
[**3**](UsersApi.md#3) | **GET** /Users/{UserId}/books | Retrieve a books object
[**3_0**](UsersApi.md#3_0) | **POST** /Users/{UserId}/books | Update books
[**4**](UsersApi.md#4) | **POST** /Users/get_list | Invoke User.get_list            
[**4_0**](UsersApi.md#4_0) | **GET** /Users/{UserId}/books/{BookId} | Retrieve a books object


# **1**
> 1(page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)

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
fields_users = '' # str | Fields to be selected (csv) (optional) (default to )
sort = 'id,name,email' # str | Sort order (optional) (default to id,name,email)
filter_name = '' # str | name attribute filter (csv) (optional) (default to )
filter_email = '' # str | email attribute filter (csv) (optional) (default to )

try:
    # Retrieve a User object            
    api_instance.1(page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)
except ApiException as e:
    print("Exception when calling UsersApi->1: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **fields_users** | **str**| Fields to be selected (csv) | [optional] [default to ]
 **sort** | **str**| Sort order | [optional] [default to id,name,email]
 **filter_name** | **str**| name attribute filter (csv) | [optional] [default to ]
 **filter_email** | **str**| email attribute filter (csv) | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **1_0**
> 1_0(post_body)

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
    api_instance.1_0(post_body)
except ApiException as e:
    print("Exception when calling UsersApi->1_0: %s\n" % e)
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

# **1_1**
> 1_1(user_id)

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
    api_instance.1_1(user_id)
except ApiException as e:
    print("Exception when calling UsersApi->1_1: %s\n" % e)
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

# **1_2**
> 1_2(user_id, post_body)

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
    api_instance.1_2(user_id, post_body)
except ApiException as e:
    print("Exception when calling UsersApi->1_2: %s\n" % e)
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

# **2**
> 2(user_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)

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
fields_users = '' # str | Fields to be selected (csv) (optional) (default to )
sort = 'id,name,email' # str | Sort order (optional) (default to id,name,email)
filter_name = '' # str | name attribute filter (csv) (optional) (default to )
filter_email = '' # str | email attribute filter (csv) (optional) (default to )

try:
    # Retrieve a User object                        
    api_instance.2(user_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)
except ApiException as e:
    print("Exception when calling UsersApi->2: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**|  | 
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **fields_users** | **str**| Fields to be selected (csv) | [optional] [default to ]
 **sort** | **str**| Sort order | [optional] [default to id,name,email]
 **filter_name** | **str**| name attribute filter (csv) | [optional] [default to ]
 **filter_email** | **str**| email attribute filter (csv) | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **2_0**
> 2_0(user_id, post_body)

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
    api_instance.2_0(user_id, post_body)
except ApiException as e:
    print("Exception when calling UsersApi->2_0: %s\n" % e)
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

# **2_1**
> 2_1(user_id, book_id)

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
    api_instance.2_1(user_id, book_id)
except ApiException as e:
    print("Exception when calling UsersApi->2_1: %s\n" % e)
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

# **3**
> 3(user_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)

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
fields_users = '' # str | Fields to be selected (csv) (optional) (default to )
sort = 'id,name,email' # str | Sort order (optional) (default to id,name,email)
filter_name = '' # str | name attribute filter (csv) (optional) (default to )
filter_email = '' # str | email attribute filter (csv) (optional) (default to )

try:
    # Retrieve a books object
    api_instance.3(user_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)
except ApiException as e:
    print("Exception when calling UsersApi->3: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **user_id** | **str**| User item | 
 **page_offset** | **int**| Page offset | [optional] [default to 0]
 **page_limit** | **int**| max number of items | [optional] [default to 10]
 **include** | **str**| related objects to include | [optional] [default to ]
 **fields_users** | **str**| Fields to be selected (csv) | [optional] [default to ]
 **sort** | **str**| Sort order | [optional] [default to id,name,email]
 **filter_name** | **str**| name attribute filter (csv) | [optional] [default to ]
 **filter_email** | **str**| email attribute filter (csv) | [optional] [default to ]

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: Not defined

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **3_0**
> 3_0(user_id, books_body)

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
    api_instance.3_0(user_id, books_body)
except ApiException as e:
    print("Exception when calling UsersApi->3_0: %s\n" % e)
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

# **4**
> 4(post_user_get_list)

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
    api_instance.4(post_user_get_list)
except ApiException as e:
    print("Exception when calling UsersApi->4: %s\n" % e)
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

# **4_0**
> 4_0(user_id, book_id)

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
    api_instance.4_0(user_id, book_id)
except ApiException as e:
    print("Exception when calling UsersApi->4_0: %s\n" % e)
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

