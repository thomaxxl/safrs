import * as ActionType from '../../action/ActionType';

const SelectedReducer = (state = {}, action) => {
    switch(action.type) {
        case ActionType.GET_SINGLE_RESPONSE: {
            return {...state, ...action.data};
        }
        default: { return state; }
    }
};

export default SelectedReducer;