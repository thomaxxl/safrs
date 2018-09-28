import { APP, config as api_config } from '../Config';
import { buildApi, get, post, patch, destroy } from 'redux-bees';
import toastr from 'toastr'
import Cookies from 'universal-cookie';

function mapIncludes(api_data){
    /*
        Relationship item attributes are not included in the jsonapi response data:
        according to the jsonapi spec this only contains "id" and "type" parameters.

        We include them ourselves here so it's easier to look it up later on
    */
    let included = api_data.included
    let items = api_data.data
    if (! included){
        return
    }
    for(let item of items){
        if(item.relationships){
            for(let relationship_name of Object.keys(item.relationships)){
                let relationship = item.relationships[relationship_name]
                if (relationship === undefined){
                    continue
                }
                if (! relationship.data){
                    item[relationship_name] = relationship
                    continue
                }
                if(relationship.data.constructor === Array){
                    // -tomany relationship
                    for(let related of relationship.data){
                        for(let included_item of included){
                            if(related.id === included_item.id){
                                related['attributes'] = included_item.attributes
                            }
                        }
                    }
                }
                else { 
                    // -toone relationship
                    var related = relationship.data
                    for(let included_item of included){
                            if(related.id === included_item.id){
                                relationship.data['attributes'] = included_item.attributes
                                //console.log('FOUND::',related['attributes'])
                            }
                        }
                }
                // map the relationship items on the top level of item (e.g. user.relationships.books.data => user.books)
                item[relationship_name] = relationship
            }
        }
        delete item.relationships;
        delete item.included;
    }
    return api_data
}

function jsonapi2bootstrap(jsonapi_data,objectKey){
    /*
        jsonapi and bootstrap have different data formats
        this function transforms data from jsonapi to bootstrap format
    */
    let data = []
    for (let item of jsonapi_data.data){
        /* map the attributes inline :
            item = { id: .. , attributes : {...} } ==> item = { id: ... , attr1: ... , attr2: ... }
        */
        let item_data = Object.assign({route:objectKey, id : item.id, relationships: item.relationships, included: jsonapi_data.included}, item.attributes)
        data.push(item_data)
    }
    jsonapi_data.data = data
    mapIncludes(jsonapi_data) 
    // var index = jsonapi_data.indexOf('relationships');
    return jsonapi_data
}

const apiEndpoints = {  
  getJsonData: {method: get, path:'/'},
  getDatas:      { method: get,     path: '/:key' },
  getData:      { method: get,     path: '/:key/:id' },
  getSearch:     { method: post,    path: '/:key/search' },
  getFilter:     { method: post,    path: '/:key/startswith' },
  search:        { method: post,    path: '/:key/search' },
  createData:    { method: post,    path: '/:key' },
  updateData:    { method: patch,   path: '/:key/:id' },
  updateRelationship_one: { method: patch,   path: '/:key/:id/:rel_name' },
  updateRelationship_many: { method:patch, path: '/:key/:key_id/:rel_name'},
  updateRelationship_delete: { method:destroy, path: '/:key/:key_id/:rel_name/:rel_id'},
  destroyData:   { method: destroy, path: '/:key/:id' },
};


const cookies = new Cookies()
let api_url = cookies.get('api_url') ? cookies.get('api_url') : api_config.URL
localStorage.setItem('url',api_url)
 
let api = buildApi(apiEndpoints, api_config);

function change_backend_url(url){
    let new_config=Object.assign({}, api_config, {baseUrl:url})
    api = buildApi(apiEndpoints,new_config);
}

let getInitialObject = () => {
    var initObj = {};
    Object.keys(APP).map(function(key, index) {
        initObj[key] = {
            offset: 0,
            limit: 50,
            data: [],
            count: 0,
            filter: {},
            select_option:[],
            search: "",
            included: []
        };
        return 0;
    });
    return initObj;
}

var datas = getInitialObject();


class ObjectApi {

  static getJsondata(url, par=null) {
    let json_api_config = api_config
    json_api_config.baseUrl = url
    let jsonapi =  buildApi(apiEndpoints, json_api_config)
    if (par === 'discover') {
      return new Promise ((resolve, reject) => {

    
        //prepare return value
        let rlt = {}
        url['collections'].map((key, index) => {
          rlt[key] = {}
          url['args'][index].split(',').map((akey, aindex) => {
            rlt[key][akey] = ''
            return true
          })
          return true
        })
        //getting json data from swagger back-end and analyze data
        url['path'].map((key, index) => {
          const req_args = {
            "page[limit]": 50,
            "include":url['args'][index]
          }
          json_api_config.baseUrl = key
          jsonapi =  buildApi(apiEndpoints, json_api_config)
          jsonapi.getJsonData(req_args)
          .then((res) => {
            res.body.data.map((rkey, rindex) => {
              const relationship = rkey['relationships']
              Object.keys(relationship).map(function(rekey, reindex) {
                if(rlt[url['collections'][index]][rekey] === '' && relationship[rekey]['data'] !== undefined) {
                  if (relationship[rekey]['data'] !== undefined) {
                    rlt[url['collections'][index]][rekey] = relationship[rekey]['data'].type
                  }
                  if (Array.isArray(relationship[rekey]['data'])) {
                    relationship[rekey]['data'].map((arkey, arindex) => {
                      if (arkey.type !== undefined) {
                        rlt[url['collections'][index]][rekey] = arkey.type
                      }
                      return true
                    })
                  }
                }
                return true
              })
              return true
            })
          })
          return true
        })
        setTimeout(() => {
          resolve(rlt)
        }, 3000)
      })
      // console.log(['rlt', rlt])
      // setTimeout(() => {
      //   return new Promise ((resolve, reject) => {
      //     resolve(rlt)
      //   })
      // },2000)
    }
    return new Promise ((resolve, reject)=>{
      jsonapi.getJsonData()
      .then((data) => {
        resolve(data)
      })
      .catch((error) => {
        reject(error)
      })
    })
  }

    static updateRelationship(objectKey, id, rel_name, data){
        change_backend_url(localStorage.getItem('url'));
        var func,post_args, request_args
        return new Promise ((resolve)=>{
            if(data.action_type === 'one'){
                func = api.updateRelationship_one
                post_args = { data : data }
                request_args = { key: APP[objectKey].API , id: id, rel_name : rel_name }
                func( request_args, post_args ).then(console.log('updated')).then((result)=>{
                            resolve(Object.assign({}, {}));
                        })
            }
            else{
                func = api.updateRelationship_many
                post_args = {data:data}
                request_args = { key: APP[objectKey].API , key_id: id, rel_name : rel_name } 
                func( request_args, post_args ).then(console.log('updated')).then((result)=>{
                    resolve(Object.assign({}, {}));
                })
            }
        })
    }

    static search(objectKey, filter, offset, limit, queryArgs){
        change_backend_url(localStorage.getItem('url'));
        return new Promise ((resolve)=>{
                var func = api.search;
                var post_args = {
                    "meta":{
                        "method":"search",
                        "args": filter
                    }
                }
                let request_args = Object.assign({ key: APP[objectKey].API,
                                                    "page[offset]": offset,
                                                    "page[limit]": limit
                                                  },
                                                 APP[objectKey].request_args ? APP[objectKey].request_args : {}, 
                                                 queryArgs)
                func( request_args,
                      post_args
                    )
                .then((result)=>{
                    datas[objectKey] = {
                        offset: datas[objectKey].offset,
                        limit: datas[objectKey].limit,
                        data: result.body.data,
                        count: result.body.meta.count,
                        filter: datas[objectKey].filter,
                        included: result.body.included ? result.body.included : []
                    };
                    resolve(Object.assign({}, datas));
                });
        });
    }

    static getAllDatas(objectKey, offset, limit, queryArgs ) {
        change_backend_url(localStorage.getItem('url'));
        return new Promise ((resolve,reject)=>{
                var search = datas[objectKey].search;
                var func = null;
                var post_args = {}
                /*if (Object.keys(filter).length != 0) {
                    func = api.getFilter;
                    post_args = {
                        "meta":{
                            "method":"startswith",
                            "args": filter
                        }
                    }
                }
                else */
                if(search){
                    func = api.getSearch;
                    post_args = {
                        "meta":{
                            "args" : {
                                "query": search
                            }
                        }
                    }
                }
                else {
                    func = api.getDatas;
                }
                if(! queryArgs){
                    queryArgs = {}
                }
                let request_args = Object.assign({ key: APP[objectKey].API,
                                                    "page[offset]": offset,
                                                    "page[limit]": limit
                                                  },
                                                 APP[objectKey].request_args ? APP[objectKey].request_args : {}, 
                                                 queryArgs)
                func( request_args,
                      post_args
                    )
                .then((result)=>{
                    let transformed_data = jsonapi2bootstrap(result.body,objectKey)
                    datas[objectKey] = {
                        offset: offset,
                        limit: limit,
                        select_option:{},
                        data: transformed_data.data,
                        search:search,
                        count: transformed_data.meta ? transformed_data.meta.count : -1,
                        filter: datas[objectKey].filter,
                    };
                    resolve(Object.assign({}, datas));
                }).catch((error) => { 
                    reject(error);
                })
        });
    }

    static saveData(objectKey, data) {
        change_backend_url(localStorage.getItem('url'));
        return new Promise((resolve, reject) => {
            var attributes = {}
            APP[objectKey].column.map(function(item, index) {
                if(item.dataField && !item.readonly){
                    attributes[item.dataField] = data[item.dataField]
                }
                return 0;
            });
            if (data.id) {
                api.updateData({
                        id: data.id,
                        key:APP[objectKey].API},
                    {data:{
                        id: data.id, 
                        type: APP[objectKey].API_TYPE, 
                        attributes: attributes}}).then(()=>{
                            resolve(data);
                        });
                
            } else {
                api.createData({
                        key:APP[objectKey].API},
                    {data:{
                        type:APP[objectKey].API_TYPE,
                        attributes: attributes}})
                    .then((result)=>{
                        if(result.status !== 201){
                            throw new Error( `Create Request: http code`+ result.code)
                        }
                        if(result && result.body && result.body.data){
                            resolve(result.body.data);
                            datas[objectKey].data.push(result.body.data)
                            datas[objectKey].data = []
                            resolve()
                        }
                        else {
                            throw new Error('Create Request: No data in response body')
                        }
                    }).catch((error) => { 
                        toastr.error('Failed to save data')
                        throw error
                    })
            }
        });
    }

    static getData(objectKey, dataId) {
        change_backend_url(localStorage.getItem('url'));
        return new Promise((resolve) => {

            let request_args = Object.assign({ key: APP[objectKey].API, id: dataId },
                                               APP[objectKey].request_args ? APP[objectKey].request_args : {} )

            api.getData(request_args).then((result)=>{
                const data = result.body.data
                const included = result.body.included
                const existingDataIndex = datas[objectKey].data.findIndex(data => data.id === dataId)
                if(existingDataIndex >= 0 ){
                    resolve(data)
                }
                else{
                    datas[objectKey].data.push(data)
                    datas[objectKey].included = included
                    jsonapi2bootstrap(datas[objectKey],objectKey)
                    resolve(datas)
                }
                /*const dataFound = Object.assign({}, datas[objectKey].data[existingDataIndex]);
                resolve(dataFound);*/
            })
        });
    }

    static deleteData(objectKey, dataIds) {
        change_backend_url(localStorage.getItem('url'));
        return new Promise((resolve) => {
            dataIds.map((dataId, index) => {
                api.destroyData({
                    id: dataId,
                    key: APP[objectKey].API})
                .then(() => {
                    resolve();
                });
                return 0;
            });
        });
    }
}
getInitialObject = datas
export {getInitialObject}
export default ObjectApi;

