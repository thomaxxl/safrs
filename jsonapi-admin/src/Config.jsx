import {FormatterList} from './components/formatters/FormatterList'
//import APP from './Config.json';
//import {ActionList} from './action/ActionList'
import ActionList from './components/actions/ActionList'

import InfoAction from './components/actions/InfoAction'

import './style/style.css'
import Cookies from 'universal-cookie';
import defaultAPP from './defaultConfig.json'

var APP = null

try { 
    APP = JSON.parse(localStorage.getItem('json'))
}
catch(err){

}

if (APP === null){
    let default_app = JSON.stringify(defaultAPP)
    //localStorage.setItem('json', default_app)
    APP = defaultAPP
}


const BaseUrl = 'http://thomaxxl.pythonanywhere.com/api'
const Timing = 5000
Object.keys(APP).map(function(key, index) {
    var initVal = {
        column: [],
        actions: Object.keys(ActionList),
        API: key,
        API_TYPE: key,
        path: "/" + key.toLocaleLowerCase(),
        menu: key,
        Title: key + " Page",
    }
    APP[key] = {...initVal, ...APP[key]};
    return 0;
});


ActionList['InfoAction'] = InfoAction

const api_objects = {}
var URL = BaseUrl
export {APP}
export {URL}
export {ActionList}
export {Timing}


export const config = {
  URL : BaseUrl,
  configureHeaders(headers) {
    const cookies = new Cookies()
    var token = cookies.get('token')

    return {
      ...headers,
      //'Authorization': `Bearer ${store.getState().session.bearerToken}`,
      'Authorization': 'Bearer ' + token
    };
  },
  afterReject({ status, headers, body }) {

    //document.location = '/login';
    if (status === 401) {
        // ie. redirect to login page
        //document.location = '/login';
        //toastr.error('Not Authorized')
    } else {
        //toastr.error('API Request Rejected', '' , TOASTR_POS)
        return Promise.reject({ status, headers, body: body });
    }
  },
};

export {config as api_config, config as Config, config as ui_config, FormatterList, api_objects}
