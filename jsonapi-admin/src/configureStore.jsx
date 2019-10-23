import {applyMiddleware, createStore} from 'redux';
import { composeWithDevTools } from 'redux-devtools-extension';
import thunk from 'redux-thunk';
import rootReducer from './reducer';

const configureStore = initialState => {
    return createStore(
        rootReducer,
	    initialState,
	        composeWithDevTools(applyMiddleware(thunk)
	    ))
};

export default configureStore;