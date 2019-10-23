import * as ActionType from '../../action/ActionType';

const analyzeReducer = (state = {showmodal:false, spinner:false}, action) => {
    switch(action.type) {
        case ActionType.GET_ANALYZE_RESPONSE: {
            // '...' spread operator clones the state
            // lodash Object assign simply clones action.courses into a new array.
            // The return object is a copy of state and overwrites the state.courses with a fresh clone of action.courses
            return {
                ...state, showmodal: action.Modal
            };
        }

        case ActionType.START_FETCHING: {
            return {
                ...state, spinner:true
            }
        }

        case ActionType.END_FETCHING: {
            return {
                ...state, spinner:false
            }
        }

        default: { return state; }
    }
};

export default analyzeReducer;