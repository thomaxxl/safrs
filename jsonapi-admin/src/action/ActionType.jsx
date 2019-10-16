/*
https://redux.js.org/basics/actions

Actions are payloads of information that send data from your application to your store. 
They are the only source of information for the store. You send them to the store using store.dispatch().
*/
export const GET_MODAL_RESPONSE = 'GET_MODAL_RESPONSE';
export const GET_FORM_RESPONSE = 'GET_FORM_RESPONSE';
export const GET_ANALYZE_RESPONSE = 'GET_ANALYZE_RESPONSE';

export const GET_RESPONSE = 'GET_RESPONSE';
export const GET_SINGLE_RESPONSE = 'GET_SINGLE_RESPONSE';
export const ADD_NEW_RESPONSE = 'ADD_NEW_RESPONSE';
export const UPDATE_EXISTING_RESPONSE = 'UPDATE_EXISTING_RESPONSE';
export const DELETE_RESPONSE = 'DELETE_RESPONSE';
export const CHANGE_INPUT_FLAG = 'CHANGE_INPUT_FLAG';
export const CHANGE_URL = 'CHANGE_URL';
export const GET_EDITOR_RESPONSE = 'GET_EDITOR_RESPONSE';

export const START_FETCHING = 'START_FETCHING';
export const END_FETCHING = 'END_FETCHING';
export const SELECT_OPTION_RESPONSE = 'SELECT_OPTION_RESPONSE';
