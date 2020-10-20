import {FormatterList, toOneFormatterFactory} from './components/formatters/FormatterList'
//import APP from './automat/Config.json';
//import {ActionList} from './action/ActionList'
import ActionList from './components/actions/ActionList'

import InfoAction from './components/actions/InfoAction'

import './style/style.css'
import Cookies from 'universal-cookie';
import APP from './Config.json'
import toastr from 'toastr'

let cookies = new Cookies()
const owner_id = cookies.get('userid', '')
const username = cookies.get('username', '')
const role = cookies.get('role', '')

const NewFormatterList = Object.assign({}, FormatterList)

function format_APP(APP){
    /*
        Custom parsing for the APP entries
    */
    Object.keys(APP).map(function(key, index) {
        var initVal = {
            column: [],
            actions: Object.keys(ActionList),
            API: key,
            API_TYPE: key,
            path: "/" + key.toLocaleLowerCase(),
            menu: key,
            Title: key + " Page",
            main_show: "name"
        }

        if(APP[key].viewer && ViewerList[APP[key].viewer]){
            APP[key].viewer = ViewerList[APP[key].viewer]
        }

        if(APP[key].container && ViewerList[APP[key].container]){
            APP[key].container = ViewerList[APP[key].container]
        }

        for(let col of APP[key].column){
            if(col.editorRenderer && NewFormatterList[col.editorRenderer]){
                col.editorRenderer = NewFormatterList[col.editorRenderer]
            }
            if(col.formatter == "toOneFormatter"){
                console.log(col)
                col.formatter = toOneFormatterFactory(col.relationship)
            }
            else if(col.formatter && NewFormatterList[col.formatter]){
                col.formatter = NewFormatterList[col.formatter]
            }
            col.relation_url = col.relation_url || col.relationship
        }

        APP[key] = {...initVal, ...APP[key]};
    })
}

const ViewerList = {}

try { 
    //APP = JSON.parse(localStorage.getItem('json'))
}
catch(err){

}

if (APP === null){
    let default_app = JSON.stringify(APP)
    //localStorage.setItem('json', default_app)
}

format_APP(APP)

const Config = {
    routes : null,
    static : APP,
    disable_api_url : true,
    title : 'Demo',
    //home : <div /> ,
    enable_login : true,
    //authenticate: authenticate,
    NavTitle: 'Demo',
    FormatterList: NewFormatterList,
    ActionList: ActionList,
    //role: role,
    //username: username,
    //email: cookies.get('email', '')
}

function get_root(){
    return "//thomaxxl.pythonanywhere.com/"
}

function get_auth(){
    return "token"
}

let BaseUrl = get_root() + '/api'
const URL = BaseUrl
cookies.set('api_url', URL)

const api_config = {
  baseUrl: BaseUrl,
  limit: 25,
  APP: APP,

  configureHeaders(headers) {
    // API Configuration: Authentication with JWT bearer token
    return {
      ...headers,
      //'Authorization': `Bearer ${store.getState().session.bearerToken}`,
      'Authorization': 'Bearer ' + get_auth()
    };
  },
  afterReject({ status, headers, body }) {
    // Show toastr popup in case the server returns a HTTP error
    const cookies = new Cookies()
    var token = cookies.get('token')
    if (status === 401) {
        toastr.error('Not Authorized')
        Config.authenticate(BaseUrl) // deauth => remove cookies
    } 
    if (status === 500 ){
        toastr.error('Internal server error')
    }
    else {
        if(status && status != 404 && status != 302){
            toastr.error(`API Request Rejected ${status}`, '' , {positionClass: "toast-top-center"})
        }
        console.log('API Request Rejected:', status)
        //cookies.remove('token');
        //cookies.remove('session');
        return Promise.reject({ status, headers, body: body });
    }
  },
}

Config.api_config = api_config
Config.logout_url = get_root() + '/admin/logout'

const api_objects = {
    
}

const Timing = 500000
export {APP, ActionList, Timing}
export {api_config, Config, Config as ui_config, NewFormatterList as FormatterList, api_objects}