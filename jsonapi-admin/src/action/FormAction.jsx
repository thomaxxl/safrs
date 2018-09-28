import * as ActionType from './ActionType';

export const getFormResponse = form => ({
    type: ActionType.GET_FORM_RESPONSE,
    form
});

export function getFormAction(form) {
    return (dispatch) => {
            dispatch(getFormResponse(form));
    };
}