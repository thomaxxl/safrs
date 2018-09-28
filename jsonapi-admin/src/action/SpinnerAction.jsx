import * as ActionType from './ActionType';

export const SpinnerStart = () => ({
    type: ActionType.START_FETCHING,
});

export const SpinnerEnd = () => ({
    type: ActionType.END_FETCHING,
});

export function getSpinnerStart() {
    return (dispatch) => {
            dispatch(SpinnerStart());
    };
}

export function getSpinnerEnd() {
    return (dispatch) => {
            dispatch(SpinnerEnd());
    };
}
