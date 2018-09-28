import {combineReducers} from 'redux';
import modalReducer from './common/modalReducer';
import formReducer from './common/formReducer';
import inputReducer from './common/inputReducer';
import analyzeReducer from './common/analyzeReducer';
import ObjectReducer from './common/objectReducer'
import selectedReducer from './common/selectedReducer';
import configReducer from './common/configReducer'


export default combineReducers({
    modalReducer,
    formReducer,
    inputReducer,
    analyzeReducer,
    object: ObjectReducer,
    selectedReducer,
    configReducer,
});