import * as ActionType from './ActionType';

export const getModalResponse = Modal => ({
    type: ActionType.GET_MODAL_RESPONSE,
    Modal
});

export function getModalAction(modal) {
    return (dispatch) => {
            dispatch(getModalResponse(modal))
    };
}

