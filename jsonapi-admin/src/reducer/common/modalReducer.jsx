import * as ActionType from '../../action/ActionType';

const modalReducer = (state = {showmodal:false}, action) => {

    switch(action.type) {
        
        case ActionType.GET_MODAL_RESPONSE: {
            // '...' spread operator clones the state
            // lodash Object assign simply clones action.courses into a new array.
            // The return object is a copy of state and overwrites the state.courses with a fresh clone of action.courses
            return {
                ...state, showmodal: action.Modal
            };
        }
        

        default: { return state; }
    }
};

export default modalReducer;