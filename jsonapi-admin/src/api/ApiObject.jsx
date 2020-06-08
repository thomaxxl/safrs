import React from 'react'
import { Link } from 'react-router-dom'
import { connect } from 'react-redux'
import { bindActionCreators } from 'redux'
import { APP, api_config, api_objects } from '../Config.jsx'
import * as ObjectAction from '../action/ObjectAction'
import * as ModalAction from '../action/ModalAction'
import * as InputAction from '../action/InputAction'
import * as SpinnerAction from '../action/SpinnerAction'
import toastr from 'toastr'
import configureStore from '../configureStore';


function getObjectFromStore(objectKey, item_id){
	/*
		retrieve an item with type objectKey from the jsonapi redux store
		This should only be called if you're sure the item is in the store
	*/
	
	const store = configureStore()
	const store_objects = store.getState()['object']
 	if(!store_objects || ! store_objects[objectKey]){
 		return null
 	}
 	const items = store_objects[objectKey].data
 	const result = items.find((item) => item.id === item_id)

 	if(!result){
 		console.warn(`${objectKey} with id ${item_id} not found `)
 	}
 	return result
}

class ApiObject extends React.Component {
	/*
		API Object Superclass

		This type of objects retreives api data from the jsonapi backend for a single instance
		we use getSingleAction to do so when the component mounts

		other actions to modify the instance are also implemented (save changes, update relationships etc)
	*/

	constructor(props){
		super(props)
		this.state = {}
		this.loadItem = this.loadItem.bind(this)
	}

	componentDidMount(){
		/*
			Fetch the api object data from the backend and load it into the state
		*/
		this._isMounted = true

		const item_id = this.props.item_id
		const api_params = this.props.api_params ? this.props.api_params : {}
		const store = configureStore()
		const store_objects = store.getState()['object']
		const objectKey = this.props.objectKey
		
		if(!store_objects[objectKey]){
			console.warn('No objects for ' + objectKey)
			return
		}

		if(store_objects[objectKey].data){
			const item = store_objects[objectKey].data.find(item => item.id == item_id)
			if(item){
				this.loadItem(item)
				return
			}
		}

		if(this.props.modalview){
			// a modal is open.. do nothing
			return
		}

		api_params['fast'] = true // sent to the backend to indicate we need fast (partial) data
		setTimeout(() => 
			this.props.action.getSingleAction(objectKey, item_id, api_params)
				.catch((error) => toastr.error(error))
				.then(() => {
					const item = this.props.api_data[objectKey].data.find(analysis => analysis.id == item_id)
					this.loadItem(item)
				}),
			2000 + Math.random() * 1000 // random delay so not everything is loaded at once
			)
		
	}

	componentWillUnmount() {
		/*
			Prevent state changes in the action promise of componentWillMount when the component is no longer mounted
		*/
    	this._isMounted = false
  	}

  	componentWillUpdate(nextProps, nextState) {
  		//console.debug('Will Update', nextState)
  		if(nextState != this.state){
  			
  		}
  	}

	shouldComponentUpdate(){
		return true	
	}

  	update(attribute, value){

  	}

  	loadItem(item){
  		if(this._isMounted && item){ // cfr. componentWillUnmount
			this.setState({	id: item.id, 
							type: item.type, 
							attributes: item.attributes, 
							relationships: item.relationships,
							...item.attributes, 
							...item.relationships})
		}
  	}

  	handleSave(attributes, attr_name){

        var key = this.props.objectKey
        let saveArgs = [this.props.objectKey, attr_name, this.props.api_data[key].offset,  this.props.api_data[key].limit, attr_name]

        return this.props.action.saveAction(...saveArgs).catch(error => {
                toastr.error(error, '')
            })
        	.then((e) => console.log(e))
            .then(toastr.success('Saved', ''))

    }

    handleSaveRelationship(newValue, row, column){
        var key = this.props.objectKey
        let rel_name = column.relation_url
        let relArgs = [ this.props.objectKey, row.id, rel_name, newValue, this.props.api_data[key].offset, this.props.api_data[key].limit ]
        this.props.action.updateRelationshipAction(...relArgs).catch(error => {
                toastr.error(error, '')
            })
        	.then((e) => console.log(e))
        	.then( toastr.success('Saved', ''))
    }

	render(){
		const name = this.state.attributes && this.state.attributes.name ? this.state.attributes.name : "default api object"
		// TO be overwritten by subclasses
		return <div>{name}</div>
	}

	getattr(attr_name){
		return this.state.attributes? this.state.attributes[attr_name] : undefined
	}
}


function get_ApiObject(key, item_id, details) {
	/*
		Create an ApiObject for the item with id from the collection specified by key
	*/

	const mapStateToProps = (state, ownProps) => ({
        objectKey: key,
        item: APP[key],
        api_data: state.object,
        inputflag: state.inputReducer,
        item_id: item_id,
        details: details,
        name : ownProps.name,
  		modalview: state.modalReducer.showmodal
    })
    
    const mapDispatchToProps = dispatch => ({
        action: bindActionCreators(ObjectAction, dispatch),
        inputaction: bindActionCreators(InputAction,dispatch),
        spinnerAction: bindActionCreators(SpinnerAction,dispatch)
    })
    
    const Api_object = api_objects[key] || ApiObject
    const Result = connect(mapStateToProps, mapDispatchToProps)(Api_object)
    const store = configureStore()

    /// todo... 
    /*function select(state) {
	  return state.some.deep.property
	}

	let currentValue
	function handleChange() {
	   alert()
	  let previousValue = currentValue
	  currentValue = select(store.getState())

	  if (previousValue !== currentValue) {
	    console.log(
	      'Some deep nested property changed from',
	      previousValue,
	      'to',
	      currentValue
	    )
	  }
	}

	const unsubscribe = store.subscribe(handleChange)
	unsubscribe()*/
	
    return Result
}

function get_ApiComponent(key, item_id, details, ref){
	/*
		get attributes, eg name, from memoizedState

		ref.current._reactInternalFiber.child.memoizedState.name
	*/
	const ApiObject =  get_ApiObject(key, item_id, details)
	return <ApiObject key={item_id} ref={ref}/>
}


export {get_ApiObject, ApiObject, get_ApiComponent, getObjectFromStore}