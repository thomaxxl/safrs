import * as ActionType from '../../action/ActionType';


const configReducer = (state = {}, action) => {
  switch(action.type) {
    case ActionType.SET_JSON_DATA: {
      return {
          ...state, ...action.data
      }
    }
    case ActionType.SET_RELATIONSHIP_DATA_JSON: {
      let mem = state
      Object.keys(mem).map(function(key, index) {
        mem[key]['relationship'].map((rkey, rindex) => {
          mem[key]['relationship'][rkey]['relationship'] = action.data[key][rkey]
          return true
        })
        return true
      })
      return { 
        ...state, ...mem
      }
    }
    case ActionType.CHANGE_ATTRIBUTES: {
      let mem = state
      mem[action.data.collectionId]['attributes'][action.data.attributesId] = action.data
      return {
        ...state, ...mem
      }
    }
    case ActionType.CHANGE_RELATIONSHIP: {
      let mem = state
      mem[action.data.collectionId]['relationship'][action.data.attributesId] = action.data
      return {
        ...state, ...mem
      }
    }
    case ActionType.CHANGE_ACTIONS: {
      let mem = state
      mem[action.data.collectionId]['actions'] = action.data.action
      return {
        ...state, ...mem
      }
    }
    case ActionType.CHANGE_OTHER: {
      let mem = state
      let val1 = {...mem[action.data.collectionId], ...action.data}
      mem[action.data.collectionId] = val1
      return {
        ...state, ...mem
      }
    }
    default: { return state; }
  }
}

export default configReducer