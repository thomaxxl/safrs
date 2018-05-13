# swagger_client.UsersApi

All URIs are relative to *https://localhost:5000*

Method | HTTP request | Description
------------- | ------------- | -------------
[**createa_userobject1**](UsersApi.md#createa_userobject1) | **POST** /Users/ | Create a User object            
[**createa_userobject2**](UsersApi.md#createa_userobject2) | **POST** /Users/{UserId}/ | Create a User object                        
[**deletea_userobject1**](UsersApi.md#deletea_userobject1) | **DELETE** /Users/{UserId}/ | Delete a User object            
[**deletefrom_userbooks1**](UsersApi.md#deletefrom_userbooks1) | **DELETE** /Users/{UserId}/books/{BookId} | Delete from User books
[**invoke_usergetlist1**](UsersApi.md#invoke_usergetlist1) | **POST** /Users/get_list | Invoke User.get_list            
[**invoke_usersendmail1**](UsersApi.md#invoke_usersendmail1) | **GET** /Users/send_mail | Invoke User.send_mail            
[**invoke_usersendmail2**](UsersApi.md#invoke_usersendmail2) | **POST** /Users/send_mail | Invoke User.send_mail            
[**retrievea_userobject1**](UsersApi.md#retrievea_userobject1) | **GET** /Users/ | Retrieve a User object            
[**retrievea_userobject2**](UsersApi.md#retrievea_userobject2) | **GET** /Users/{UserId}/ | Retrieve a User object                        
[**retrieveabooksobject1**](UsersApi.md#retrieveabooksobject1) | **GET** /Users/{UserId}/books | Retrieve a books object
[**retrieveabooksobject2**](UsersApi.md#retrieveabooksobject2) | **GET** /Users/{UserId}/books/{BookId} | Retrieve a books object
[**updatea_userobject1**](UsersApi.md#updatea_userobject1) | **PATCH** /Users/{UserId}/ | Update a User object            
[**updatebooks1**](UsersApi.md#updatebooks1) | **POST** /Users/{UserId}/books | Update books


# **createa_userobject1**
> createa_userobject1(post_body)

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
    api_instance.createa_userobject1(post_body)
except ApiException as e:
    print("Exception when calling UsersApi->createa_userobject1: %s\n" % e)
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

# **createa_userobject2**
> createa_userobject2(user_id, post_body)

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
    api_instance.createa_userobject2(user_id, post_body)
except ApiException as e:
    print("Exception when calling UsersApi->createa_userobject2: %s\n" % e)
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

# **deletea_userobject1**
> deletea_userobject1(user_id)

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
    api_instance.deletea_userobject1(user_id)
except ApiException as e:
    print("Exception when calling UsersApi->deletea_userobject1: %s\n" % e)
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

# **deletefrom_userbooks1**
> deletefrom_userbooks1(user_id, book_id)

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
    api_instance.deletefrom_userbooks1(user_id, book_id)
except ApiException as e:
    print("Exception when calling UsersApi->deletefrom_userbooks1: %s\n" % e)
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

# **invoke_usergetlist1**
> invoke_usergetlist1(post_user_get_list)

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
    api_instance.invoke_usergetlist1(post_user_get_list)
except ApiException as e:
    print("Exception when calling UsersApi->invoke_usergetlist1: %s\n" % e)
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

# **invoke_usersendmail1**
> invoke_usersendmail1(page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email, varargs=varargs)

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
page_offset = 0 # int | Page offset (optional) (default to 0)
page_limit = 10 # int | max number of items (optional) (default to 10)
include = '' # str | related objects to include (optional) (default to )
fields_users = '' # str | Fields to be selected (csv) (optional) (default to )
sort = 'id,name,email' # str | Sort order (optional) (default to id,name,email)
filter_name = '' # str | name attribute filter (csv) (optional) (default to )
filter_email = '' # str | email attribute filter (csv) (optional) (default to )
varargs = 'varargs_example' # str | send_mail arguments (optional)

try:
    # Invoke User.send_mail            
    api_instance.invoke_usersendmail1(page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email, varargs=varargs)
except ApiException as e:
    print("Exception when calling UsersApi->invoke_usersendmail1: %s\n" % e)
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
 **varargs** | **str**| send_mail arguments | [optional] 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **invoke_usersendmail2**
> invoke_usersendmail2(post_user_send_mail)

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

try:
    # Invoke User.send_mail            
    api_instance.invoke_usersendmail2(post_user_send_mail)
except ApiException as e:
    print("Exception when calling UsersApi->invoke_usersendmail2: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **post_user_send_mail** | [**PostUserSendMail**](PostUserSendMail.md)| Send an email | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **retrievea_userobject1**
> retrievea_userobject1(page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)

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
    api_instance.retrievea_userobject1(page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)
except ApiException as e:
    print("Exception when calling UsersApi->retrievea_userobject1: %s\n" % e)
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

# **retrievea_userobject2**
> retrievea_userobject2(user_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)

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
    api_instance.retrievea_userobject2(user_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)
except ApiException as e:
    print("Exception when calling UsersApi->retrievea_userobject2: %s\n" % e)
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

# **retrieveabooksobject1**
> retrieveabooksobject1(user_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)

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
    api_instance.retrieveabooksobject1(user_id, page_offset=page_offset, page_limit=page_limit, include=include, fields_users=fields_users, sort=sort, filter_name=filter_name, filter_email=filter_email)
except ApiException as e:
    print("Exception when calling UsersApi->retrieveabooksobject1: %s\n" % e)
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

# **retrieveabooksobject2**
> retrieveabooksobject2(user_id, book_id)

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
    api_instance.retrieveabooksobject2(user_id, book_id)
except ApiException as e:
    print("Exception when calling UsersApi->retrieveabooksobject2: %s\n" % e)
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

# **updatea_userobject1**
> updatea_userobject1(user_id, post_body)

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
    api_instance.updatea_userobject1(user_id, post_body)
except ApiException as e:
    print("Exception when calling UsersApi->updatea_userobject1: %s\n" % e)
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

# **updatebooks1**
> updatebooks1(user_id, books_body)

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
    api_instance.updatebooks1(user_id, books_body)
except ApiException as e:
    print("Exception when calling UsersApi->updatebooks1: %s\n" % e)
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

