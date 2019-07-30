import jsonapi_requests, logging, requests, unittest, time
from jsonapi_requests.orm import OrmApi, AttributeField, RelationField, ApiModel
from threading import Thread

import sys

sys.path.append("..")


class Api(OrmApi):
    def disco(self, obj_name, obj_type=None, attributes=[], relations=[]):
        """
            Discover API resource objects and create a class from the result
            If there's a "sample" object available in the api, the discovered
            attributes will be added to the the result class

            class Person(jsonapi_requests.orm.ApiModel):
                class Meta:
                   type = 'person'
                   api = api

                name = jsonapi_requests.orm.AttributeField('name')
                married_to = jsonapi_requests.orm.RelationField('married-to')

        """

        if obj_type == None:
            obj_type = obj_name

        # Create the Meta class
        meta_class = type("Meta", (object,), {"type": obj_type, "api": self})

        # Connect to the resource collection
        endpoint = self.endpoint(obj_type)

        try:
            response = endpoint.get()
        except jsonapi_requests.request_factory.ApiConnectionError as exc:
            raise

        if response.data.as_data():
            # Use the first item as test sample
            test_id = response.data.as_data()[0]["id"]
            endpoint = self.endpoint("{}/{}".format(obj_type, test_id))
            response = endpoint.get()
            data = response.data.as_data()
            attributes += data.get("attributes", {}).keys()
            relations += data.get("relationships", {}).keys()

        properties = {"Meta": meta_class}
        attr_properties = {attr: AttributeField(attr) for attr in attributes}
        properties.update(attr_properties)
        rel_properties = {rel: RelationField(rel) for rel in relations}
        properties.update(rel_properties)

        api_object = type(obj_name, (ApiModel,), properties)

        setattr(self, obj_name, api_object)
        return api_object


import ctypes
import threading
import time


# inspired by https://github.com/mosquito/crew/blob/master/crew/worker/thread.py
def kill_thread(thread: threading.Thread, exception: BaseException = KeyboardInterrupt) -> None:
    if not thread.isAlive():
        return

    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread.ident), ctypes.py_object(exception))

    if res == 0:
        raise ValueError("nonexistent thread id")
    elif res > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")

    while thread.isAlive():
        time.sleep(0.01)


def call_method(resource, method, data={}):
    """
        
    """

    endpoint = resource + "/" + method

    try:
        r = requests.post(endpoint, json=data)
    except Exception as exc:
        log.error("Error while calling C&C method {} on resource {}".format(method, endpoint))
        return

    if not r.status_code == requests.codes.ok:
        log.error("Error ({}) while calling C&C method {} on resource {}".format(r.status_code, method, resource))
        return

    data = r.json()
    result = data.get("meta", {}).get("result")
    log.debug("C&C Result: {}".format(result))
    return result


API_ROOT = "http://0.0.0.0:5000/"


def app_thread():
    from examples.demo_relationship import app


class Test_Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_thread = Thread(target=app_thread)
        cls.app_thread.start()
        time.sleep(2)
        cls.api = Api.config(
            {
                "API_ROOT": API_ROOT,
                "AUTH": ("basic_auth_login", "basic_auth_password"),
                "VALIDATE_SSL": False,
                "TIMEOUT": 1,
            }
        )
        cls.api.disco("User", "Users")
        cls.api.disco("Book", "Books")

    @classmethod
    def tearDownClass(cls):
        time.sleep(1)
        kill_thread(cls.app_thread)
        time.sleep(1)

    def test_0_create_user(self):
        user = self.api.User()
        user.name = "TEST_NAME"
        user.save()
        self.assertEqual(type(user.id), str)
        for user in self.api.User.get_list():
            print(user.id, user.name)

        user.delete()

    def test_1_add_book(self):
        user = self.api.User()
        user.save()
        book = self.api.Book()
        book.name = "BOOK_TEST_NAME"
        book.save()
        user.books.append(book)
        user.save()
        print("Book:", user.books[0].id)
        book.delete()
        user.delete()


log = logging.getLogger()
