import * as ActionType from '../../action/ActionType';
//import URL from '../../Config.js'
import Cookies from 'universal-cookie';

const cookies = new Cookies()
if(!cookies.get('api_url') ){
    cookies.set('api_url', '//thomaxxl.pythonanywhere.com/api' )
}
var api_url = cookies.get('api_url')

const inputReducer = (state = {flag:true,url:api_url}, action) => {

    switch(action.type) {
        case ActionType.CHANGE_INPUT_FLAG: {
            return {
                ...state, flag: action.flag
            };
        }
        case ActionType.CHANGE_URL: {
            return {
                ...state, url: action.url
            };
        }

        default: { return state; }
    }
};

export default inputReducer;
