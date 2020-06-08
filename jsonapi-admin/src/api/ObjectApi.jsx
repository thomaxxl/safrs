/*
    The ObjectApi defines the CRUD methods on the API backend
*/
import React from 'react';
import { APP, api_config } from '../Config.jsx';
import { buildApi, get, post, patch, destroy } from 'redux-bees';
import toastr from 'toastr'
import Cookies from 'universal-cookie';
//import configureStore from '../configureStore';


/*
    JSON:API generic CRUD endpoints:
    the frontend will retrieve and update the backend database through these URL paths
*/

const apiEndpoints = {  
  getCollection: { method: get,     path: '/:key' },
  getItem:       { method: get,     path: '/:key/:id' },
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


// Get the API url stored in the cookie
const cookies = new Cookies()
let api_url = cookies.get('api_url') ? cookies.get('api_url') : api_config.URL
localStorage.setItem('url',api_url)
 
/* 
    Construct the API by generating the endpoints from
    - The generic apiEndpoints
    - The api configuration routes (in the config.json)

    E.g.: if the config contains a "Case" key with following attributes:

    "path": "/Cases",
    "API": "Cases",
    "API_TYPE": "Case",
    
    Then the corresponding endpoints will be 

    getCollection => /Cases
    getItem => /Cases/{CaseId}

    etc. (check the API swagger to view the available endpoints for each object)
*/
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
            limit: api_config.limit || 25,
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

var api_objects = getInitialObject();


function wrapped_Promise(promise){
    return promise
}

class ObjectApi{
    /*
        CRUD actions for the JSON:API backend
    */
    static getItem(objectKey, dataId, requestArgs) {
        /*
            Retrieve a single item from the collection specified by the objectKey with the given id `dataId`
        */

        if(!dataId){
            console.log('No dataId for', objectKey)

        }
        change_backend_url(localStorage.getItem('url'));
        let result = new Promise((resolve) => {

            let request_args = Object.assign({key: APP[objectKey].API, id: dataId, single: true },
                                              APP[objectKey].request_args ? APP[objectKey].request_args : {} )

            if(requestArgs){
                request_args = Object.assign(request_args, requestArgs)
            }

            api.getItem(request_args).then((result)=>{
                const data = result.body.data
                const included = result.body.included
                const existingDataIndex = api_objects[objectKey].data.findIndex(data => data.id === dataId)
                if(existingDataIndex >= 0){
                    resolve(data)
                }
                else{
                    api_objects[objectKey].data.push(data)
                    api_objects[objectKey].included = included
                    jsonapi2bootstrap(api_objects[objectKey],objectKey)
                    resolve(api_objects)
                }
                /*const dataFound = Object.assign({}, api_objects[objectKey].data[existingDataIndex]);
                resolve(dataFound);*/
            })
        });
        return wrapped_Promise(result)
    }


    static getCollection(objectKey, offset, limit, queryArgs) {
        /*
            Retrieve all the items from the collection at the specified offset with the specified limit
        */
        console.log('getCollection', offset, limit)
        if(offset === undefined){
            // todo: get the current offset
            offset = 0
        }
        if(limit === undefined){
            // todo: get the current limit
            limit = api_config.limit || 25
        }
        change_backend_url(localStorage.getItem('url'));
        let result = new Promise ((resolve,reject)=>{
                var search = api_objects[objectKey].search;
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
                    func = api.getCollection;
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
                    if(!result || ! result.body){
                        console.warn(result)
                        throw "invalid result"
                    }
                    let transformed_data = jsonapi2bootstrap(result.body,objectKey)
                    api_objects[objectKey] = {
                        offset: offset,
                        limit: limit,
                        select_option:{},
                        data: transformed_data.data,
                        search:search,
                        count: transformed_data.meta ? transformed_data.meta.count : -1,
                        filter: api_objects[objectKey].filter,
                    };
                    resolve(Object.assign({}, api_objects));
                }).catch((error) => { 
                    reject(error);
                })
        });
        return wrapped_Promise(result)
    }

    static saveData(objectKey, data) {
        /*
            Save or create an item to the backend
        */
        //change_backend_url(localStorage.getItem('url'));
        let result = new Promise((resolve, reject) => {
            var attributes = {}
            APP[objectKey].column.map(function(item, index) {
                if(item.dataField && !item.readonly){

                    attributes[item.dataField] = data[item.dataField]
                }
                return 0;
            });
            
            if (data.id) {
                /*
                    id is specified => update the item with the given id
                */
                let item_data = {
                                id: data.id, 
                                type: APP[objectKey].API_TYPE, 
                                attributes: attributes
                            }
                api.updateData({ // => http patch
                    id: data.id,
                    key: APP[objectKey].API},
                    {data: item_data})
                .then(()=>{
                    resolve(data);
                })
            } else {
                /*
                    No id specified => create a new item
                */
                api.createData({
                        key:APP[objectKey].API},
                        {data:{
                            type:APP[objectKey].API_TYPE,
                            attributes: attributes}})
                    .then((result)=>{
                        if(!result){
                            throw new Error(`Create Data Request Failed`)
                        }
                        if(result.status !== 201){
                            console.error(result)
                            throw new Error(`Create Request: http code`+ result.code)
                        }
                        if(result && result.body && result.body.data){
                            //TODO: update
                            resolve(result.body.data);
                            api_objects[objectKey].data.push(result.body.data)
                            api_objects[objectKey].data = []
                            resolve(api_objects)
                        }
                        else {
                            throw new Error('Create Request: No data in response body')
                        }
                    }).catch((error) => { 
                        console.error(error)
                        if(error.body && error.body.errors){
                            console.log(error.body.errors)
                            error = error.body.errors[0].detail
                            toastr.error(String(error))
                        }
                        else{
                            toastr.error('Failed to save data' + String(error))
                        }
                    })
            }
        });
        return wrapped_Promise(result)
    }

    static updateRelationship_one(objectKey, id, rel_name, data){
        /*
            Update a to-one relationship
        */
        change_backend_url(localStorage.getItem('url'));
        var func,post_args, request_args
        
        let result = new Promise ((resolve)=>{
            func = api.updateRelationship_one
            post_args = { data : data }
            request_args = { key: APP[objectKey].API , id: id, rel_name : rel_name }
            func(request_args, post_args ).then(console.log('updated')).then((result)=>{
                        console.log(result.body)
                        resolve(Object.assign({}, result.body));
                })
            })
        return wrapped_Promise(result)
    }

    static updateRelationship(objectKey, id, rel_name, data){
        /*
            Update a relationship, which can be either to-one or a to-many
        */
        change_backend_url(localStorage.getItem('url'));
        var func,post_args, request_args
        let result =  new Promise ((resolve)=>{
            if(data === null || data.action_type === 'one'){
                func = api.updateRelationship_one
                post_args = { data : data }
                request_args = { key: APP[objectKey].API , id: id, rel_name : rel_name }
                func(request_args, post_args ).then((result)=>{
                            resolve(Object.assign({}, result.body));
                        })
            }
            else{
                func = api.updateRelationship_many
                post_args = {data:data}
                request_args = { key: APP[objectKey].API , key_id: id, rel_name : rel_name } 
                func( request_args, post_args ).then((result)=>{
                    resolve(Object.assign({}, result.body));
                })
            }
        })
        return wrapped_Promise(result)
    }

    static deleteData(objectKey, dataIds) {
        /*
            Delete the items with ids specified in the dataIds array from the collection 
        */

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

    static search(objectKey, filter, offset, limit, queryArgs){
        /*
            Call the api method "search" 
        */

        change_backend_url(localStorage.getItem('url'));
        let result = new Promise ((resolve)=>{
                var func = api.search;
                var post_args = {
                    "meta":{
                        "method":"search",
                        "args": filter
                    }
                }
                console.log(APP)
                console.log(objectKey)
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
                    api_objects[objectKey] = {
                        offset: api_objects[objectKey].offset,
                        limit: api_objects[objectKey].limit,
                        data: result.body.data,
                        count: result.body.meta.count,
                        filter: api_objects[objectKey].filter,
                        included: result.body.included ? result.body.included : []
                    };
                    resolve(Object.assign({}, api_objects));
                });
        });
        return wrapped_Promise(result)
    }
}


function type2route(type){
    /*
        the api data is stored in the redux store under their routes
        here we convert the type to the appropriate route
    */
    for(let key of Object.keys(api_config.APP)){
        if(api_config.APP[key].API_TYPE == type){
            return type
        }
    }
    // console.warn(`Invalid API object type ${type}: No Route, check Config.json`)
}

function type2route(type){
    /*
        the api data is stored in the redux store under their routes
        here we convert the type to the appropriate route
    */
    for(let key of Object.keys(api_config.APP)){
        if(api_config.APP[key].API_TYPE == type){
            return key
        }
    }
    // console.warn(`Invalid API object type ${type}: No Route, check Config.json`)
}


function add_to_store(item){
    const route = type2route(item.type)
    if(api_objects[route] === undefined){
        console.warn(`Invalid route ${route} for ${route} (${item.type})`)
        console.log(api_objects)
        return
    }
    for(let stored_item of api_objects[route].data){
        if(item.id == stored_item.id){
            // item is already in the store
            return
        }
    }
    api_objects[route].data.push(item)
}

function mapIncludes(api_data){
    /*
        Relationship item attributes are not included in the jsonapi response data:
        according to the jsonapi spec this only contains "id" and "type" parameters, e.g.:
        
        "relationships": {
          "images": {
            "data": [
              {
                "id": "048c37ce-fb75-4ff5-8016-178703531bf1",
                "type": "Images"
              }
            ]
          }
        }
        ...<snipped/>...
        "included": [{
                          "attributes": {
                            "name": "Item_2537_2018",
                          },
                          "id": "048c37ce-fb75-4ff5-8016-178703531bf1",
                          "type": "Images"
                        }
                      ],
        
        in the above snippet:
            "images" is the name of a relationship
            this relationship contains a single image, the attributes (and other info) are given in the "included" part

        Check the swagger to understand the jsonapi structure!

        this function maps the included items so it's easier to look it up later on  
    */
    let included = api_data.included  || []
    let items = api_data.data || []
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
                    /* -to-many relationship :
                        
                    */ 
                    for(let related of relationship.data){
                        for(let included_item of included){
                            add_to_store(included_item)
                            if(related.id === included_item.id){
                                related['attributes'] = included_item.attributes
                            }
                        }
                    }
                }
                else { 
                    // -to-one relationship
                    var related = relationship.data
                    for(let included_item of included){
                        add_to_store(included_item)
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
        for(const [attr, val] of Object.entries(item.attributes)){
            item[attr] = val
        }
    }
    console.log(api_objects)
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
        let item_data = {route:objectKey, id : item.id, type: item.type, relationships: item.relationships, included: jsonapi_data.included, attributes: item.attributes}
        data.push(item_data)
    }
    jsonapi_data.data = data
    mapIncludes(jsonapi_data) 
    return jsonapi_data
}


//getInitialObject = api_objects
export {api_objects as getInitialObject}
export default ObjectApi;
