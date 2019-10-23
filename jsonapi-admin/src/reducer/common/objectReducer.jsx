import * as ActionType from '../../action/ActionType';
import { getInitialObject } from '../../api/ObjectApi';


const ObjectReducer = (state = getInitialObject, action) => {
    switch(action.type) {

        
        case ActionType.GET_RESPONSE: {
            return {...state, ...action.data};
        }

        case ActionType.UPDATE_EXISTING_RESPONSE: {
            var order=""
            state[action.objectKey].data.forEach((state_item, index) =>{
                if(state_item.id === action.change_id){
                    order = index
                }
            })
            if(!action.rel_or_not)
            {
                state[action.objectKey].data[order][action.dataField] = action.item[action.dataField]
                return {...state}
            }
            else if(action.rel_or_not === 1){
                state[action.objectKey].data[order][action.dataField].data = action.item
                var atr = action.dataField + '_id'
                state[action.objectKey].data[order][atr] = action.item.id
                return {...state}
            }else if(action.rel_or_not === 2){
                state[action.objectKey].data[order][action.dataField].data = action.item
                return {...state}
            }
        }
        case ActionType.SELECT_OPTION_RESPONSE: {
            state[action.route].select_option[action.objectKey] = action.data.data
            return state;
        }

        default: { return state; }
        
    }
};


export default ObjectReducer;