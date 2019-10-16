import * as ActionType from './ActionType';

export const getInputResponse = flag => ({
    type: ActionType.CHANGE_INPUT_FLAG,
    flag
});

export function getInputAction(flag) {
    return (dispatch) => {
            dispatch(getInputResponse(flag));
    };
}


export const getUrlResponse = url => ({
    type: ActionType.CHANGE_URL,
    url
});

export function getUrlAction(url) {
    return (dispatch) => {
            dispatch(getUrlResponse(url));
    };
}