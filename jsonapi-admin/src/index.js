import React from 'react';
import {render} from 'react-dom';

import 'bootstrap/dist/js/bootstrap';
import 'bootstrap/dist/css/bootstrap.min.css';
import 'toastr/build/toastr.min.css';
import 'font-awesome/css/font-awesome.css';
import 'react-bootstrap-table/dist/react-bootstrap-table.min.css';
import {Provider} from 'react-redux';

import configureStore from './configureStore';
import App from './components/App';

import registerServiceWorker from './registerServiceWorker';

const store = configureStore();
export default store;

render(
    <Provider store={store}>
        <App />
    </Provider>,
    document.getElementById('root')
);

registerServiceWorker();
