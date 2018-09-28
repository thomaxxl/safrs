import * as ActionType from 'action/ActionType';
import ObjectApi from 'api/ObjectApi'

export function analyzejsonrelationship(data) {
  const D = data.body.paths
  let getPath = {}
  getPath['path'] = []
  getPath['args'] = []
  getPath['collections'] = []
  const JS = {}
  Object.keys(D).map((key) => {
    const len = key.length
    if(key[0] === '/' && key[len-1] === '/') {
      let gas = 0;
      for (let i = 0 ; i < len ; i+=1) {
        if (key[i] === '/') gas += 1
      }
      if(gas === 2) {
        let rlt = key.substring(1, len-1)
        getPath['collections'].push(rlt)
        JS[rlt] = {}
        D[key].get.parameters.map((key, index) => {
          let relationship = []
          if(key.name === 'include') {
            relationship = key.default.split(',')
            JS[rlt]['relationship'] = relationship
          }
          return true
        })
        let req = ''
        JS[rlt]['relationship'].map((key, index) => {
          req += key + ","
          return true
        })
        let sreq = req.substring(0, req.length-1)
        getPath['path'].push('http://'+data.body.host+'/'+rlt)
        getPath['args'].push(sreq)      
      }
    }
    return true
  })
  return (dispatch) => {
    ObjectApi.getJsondata(getPath, 'discover')
    .then((res) => {
      dispatch(SetJsonRelationship(res))
    })
  }
}

export function analyzejson(data) {
  //parsing the collections
  //collection's starting '/' and end with '/' and contain only 2 '/'s
  const D = data.body.paths
  const JS = {}
  Object.keys(D).map((key) => {
    const len = key.length
    if(key[0] === '/' && key[len-1] === '/') {
      let gas = 0;
      for (let i = 0 ; i < len ; i+=1) {
        if (key[i] === '/') gas += 1
      }
      if(gas === 2) {
        let rlt = key.substring(1, len-1)
        JS[rlt] = {}
        D[key].get.parameters.map((key, index) => {
          let relationship = []
          let attributes = []
          if(key.name === 'include') {
            relationship = key.default.split(',')
            JS[rlt]['relationship'] = relationship
          }
          if(key.name === 'sort') {
            attributes = key.default.split(',')
            let realatt = [];
            attributes.map((key, index) => {
              if(key.indexOf('_id') > -1) {
              } else {
                realatt.push(key)
              }
              return true
            })
            JS[rlt]['attributes'] = realatt
            JS[rlt]['attributes1'] = attributes
          }
          return true
        })
        JS[rlt]['actions'] = ["CreateAction", "EditAction", "DeleteAction", "InfoAction"]
        //setting_main_show
        let show = ''
        JS[rlt]['attributes'].map((key, index) => {
          if (!(key.indexOf('_id') > -1) && show === '') {
            show = key
          }
          return true
        })
        JS[rlt]['main_show'] = show
        JS[rlt]['path'] = "/"+rlt.toLowerCase()
        JS[rlt]['API'] = rlt
        JS[rlt]['API_TYPE'] = rlt
        JS[rlt]['menu'] = rlt
        JS[rlt]['Title'] = rlt
        let req = ''
        JS[rlt]['relationship'].map((key, index) => {
          req += key + ","
          return true
        })
        let sreq = req.substring(0, req.length-1)
        JS[rlt]['request_args'] = {include : sreq}

        //relationship data processing
        JS[rlt]['relationship'].map((key, index) => {
          JS[rlt]['relationship'][key] = {}
          return true
        })
        JS[rlt]['relationship'].map((key, index) => {
          JS[rlt]['relationship'][key]['text'] = key.charAt(0).toUpperCase() + key.slice(1)
          const check_att = key+'_id'
          if (JS[rlt]['attributes1'].includes(check_att)) {
            JS[rlt]['relationship'][key]['dataField'] = check_att
            JS[rlt]['relationship'][key]['formatter'] = 'toOneFormatter'
            JS[rlt]['relationship'][key]['editorRenderer'] = 'toOneEditor'
          } else {
            JS[rlt]['relationship'][key]['dataField'] = key
            JS[rlt]['relationship'][key]['formatter'] = 'toManyFormatter'
            JS[rlt]['relationship'][key]['editorRenderer'] = 'ToManyRelationshipEditor'
          }
          JS[rlt]['relationship'][key]['relation_url'] = key
          JS[rlt]['relationship'][key]['type'] = 'text'
          JS[rlt]['relationship'][key]['relationship'] = ''
          if (key === "") JS[rlt]['relationship'] = []
          return true
        })
        //attributes processing
        JS[rlt]['attributes'].map((key, index) => {
          JS[rlt]['attributes'][key] = {}
          JS[rlt]['attributes'][key]['text'] = key.charAt(0).toUpperCase() + key.slice(1)
          JS[rlt]['attributes'][key]['dataField'] = key
          JS[rlt]['attributes'][key]['sort'] = true
          JS[rlt]['attributes'][key]['type'] = 'text'
          // JS[rlt]['attributes'][key]['placeholder'] = 'Type '+key
          return true
        })
      }
    }
    return true
  })
  return (dispatch) => {
    dispatch(SetJsonData(JS));
  };
}

export function local_to_reducer(data) {
  return (dispatch) => {
    dispatch(SetJsonData(data))
  }
}

export const SetJsonRelationship = data => ({
  type: ActionType.SET_RELATIONSHIP_DATA_JSON,
  data
})

export const SetJsonData = data => ({
  type: ActionType.SET_JSON_DATA,
  data
});

export function change_attributes(data) {
  return (dispatch) => {
    dispatch(changeattributes(data))
  }
}

export const changeattributes = data => ({
  type: ActionType.CHANGE_ATTRIBUTES,
  data
})

export function change_relationship(data) {
  return (dispatch) => {
    dispatch(changerelationship(data))
  }
}

export const changerelationship = data => ({
  type:ActionType.CHANGE_RELATIONSHIP,
  data
})

export function change_actions(data) {
  return (dispatch) => {
    dispatch(changeactions(data))
  }
}

export const changeactions = data => ({
  type: ActionType.CHANGE_ACTIONS,
  data
})

export function change_other(data) {
  return (dispatch) => {
    dispatch(changeother(data))
  }
}

export const changeother = data => ({
  type: ActionType.CHANGE_OTHER,
  data
})