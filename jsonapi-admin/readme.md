# jsonapi-admin

[LIVE DEMO](http://thomaxxl.pythonanywhere.com/ja/index.html#/)

(beta) reactjs+redux CRUD frontend for [jsonapi](http://jsonapi.org) backend

## Installation

```
git clone https://github.com/thomaxxl/jsonapi-admin
cd jsonapi-admin
npm install
npm start
```

## Configuration

Interface configuration is declared in [src/Config.js](src/Config.js) (Modify this file to customize the app)

```javascript
const BaseUrl = 'http://thomaxxl.pythonanywhere.com'
```

and [src/Config.json](src/Config.json)

```javascript
{
  "People": {
    "column": [
      {
        "text": "Name",
        "dataField": "name",
        "type": "text",
        "plaintext": "Name"
      },
      {
        "text": "Email",
        "dataField": "email",
        "plaintext": "Email"
      },
      {
        "text": "Comment",
        "dataField": "comment",
        "plaintext": "Comment"
      },
      {
        "text": "Books_read",
        "dataField": "books_read",
        "relation_url": "books_read",
        "type": "text",
        "relationship": "Books",
        "plaintext": "Books_read"
      },
      {
        "text": "Books_written",
        "dataField": "books_written",
        "relation_url": "books_written",
        "type": "text",
        "relationship": "books_written",
        "plaintext": "Books_written"
      },
      {
        "text": "Reviews",
        "dataField": "reviews",
        "relation_url": "reviews",
        "type": "text",
        "relationship": "Reviews",
        "plaintext": "Reviews"
      }
    ],
    "actions": [
      "CreateAction",
      "EditAction",
      "DeleteAction",
      "CustomAction"
    ],
    "API": "People",
    "API_TYPE": "User",
    "path": "/people",
    "menu": "People",
    "Title": "People",
    "main_show": "name",
    "request_args": {
      "include": "books_read,books_written,reviews",
      "sort": "name"
    }
  },
  "Books": {
    "column": [
      {
        "text": "Title",
        "dataField": "title",
        "type": "text",
        "placeholder": "Title name.",
        "sort": true,
        "plaintext": "Title"
      },
      {
        "text": "Author",
        "dataField": "author_id",
        "relation_url": "author",
        "type": "text",
        "relationship": "People",
        "plaintext": "Author"
      },
      {
        "text": "Publisher",
        "dataField": "publisher_id",
        "relation_url": "publisher",
        "type": "text",
        "relationship": "Publishers",
        "plaintext": "Publisher"
      },
      {
        "text": "Reader",
        "dataField": "reader_id",
        "relation_url": "reader",
        "type": "text",
        "relationship": "People",
        "plaintext": "Reader"
      },
      {
        "text": "Reviews",
        "dataField": "reviews",
        "relation_url": "reviews",
        "type": "text",
        "relationship": "Reviews",
        "plaintext": "Reviews"
      }
    ],
    "actions": [
      "CreateAction",
      "EditAction",
      "DeleteAction",
      "InfoAction"
    ],
    "API": "Books",
    "API_TYPE": "Book",
    "path": "/books",
    "menu": "Books",
    "Title": "Books",
    "main_show": "title",
    "request_args": {
      "include": "reader,author,publisher,reviews"
    }
  },
  "Reviews": {
    "column": [
      {
        "text": "Review",
        "dataField": "review",
        "type": "text",
        "placeholder": "Type review.",
        "sort": true,
        "plaintext": "Review"
      },
      {
        "text": "Person",
        "dataField": "reader_id",
        "relation_url": "person",
        "type": "text",
        "relationship": "People",
        "plaintext": "Person"
      },
      {
        "text": "Book",
        "dataField": "book_id",
        "relation_url": "book",
        "type": "text",
        "relationship": "Books",
        "plaintext": "Book"
      }
    ],
    "actions": [
      "CreateAction",
      "EditAction",
      "DeleteAction",
      "InfoAction"
    ],
    "API": "Reviews",
    "API_TYPE": "Review",
    "path": "/reviews",
    "menu": "Reviews",
    "Title": "Reviews",
    "main_show": "review",
    "request_args": {
      "include": "person,book"
    }
  },
  "Publishers": {
    "column": [
      {
        "text": "Name",
        "dataField": "name",
        "type": "text",
        "placeholder": "Type name.",
        "sort": true,
        "plaintext": "Name"
      },
      {
        "text": "Books",
        "dataField": "books",
        "relation_url": "books",
        "type": "text",
        "relationship": "Books",
        "plaintext": "Books"
      }
    ],
    "actions": [
      "CreateAction",
      "EditAction",
      "DeleteAction",
      "InfoAction"
    ],
    "API": "Publishers",
    "API_TYPE": "Publisher",
    "path": "/publishers",
    "menu": "Publishers",
    "Title": "Publishers",
    "main_show": "name",
    "request_args": {
      "include": "books"
    }
  }
}
```
