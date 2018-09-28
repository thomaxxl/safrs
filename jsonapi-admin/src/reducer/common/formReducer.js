import * as ActionType from '../../action/ActionType';
const formReducer = (state = {form:true}, action) => {

    switch(action.type) {
        case ActionType.GET_FORM_RESPONSE: {
            // '...' spread operator clones the state
            // lodash Object assign simply clones action.courses into a new array.
            // The return object is a copy of state and overwrites the state.courses with a fresh clone of action.courses
            return {
                ...state, form: action.form
            };
        }

        default: { return state; }
    }
};

export default formReducer;