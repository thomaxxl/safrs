import React from 'react'
import { faTimes } from '@fortawesome/fontawesome-free-solid'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
// import toastr from 'toastr'
import * as Param from '../../Config';
import Select from 'react-select'
import 'react-select/dist/react-select.css';
import ObjectApi from '../../api/ObjectApi'
import { connect } from 'react-redux'
import { bindActionCreators } from 'redux'
import * as ObjectAction from '../../action/ObjectAction'

function cellFormatter(cell, row) {

    return <strong><div className="call">{ JSON.stringify(cell) }</div></strong>
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

// function lookupIncluded(item, row){
// 	/*
// 		lookup the relationship item in the row "included" data
// 		this follows the jsonapi format:

// 		item : { "id" : .. , "type" : .. }
// 		row : { "data" : .. , "links" : .. , "relationships" : }
// 	*/
	
// 	if(!item.id || !item.type){
// 		toastr.error('Data Error')
// 	}
// 	if(!row || !row.included || !row.relationships){
// 		return <div/>
// 	}
// 	for(let included of row.included){
// 		if(included.type === item.type && included.id === item.id){
// 			return included
// 		}
// 	}
// 	return null
// }

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

function toOneFormatter(cell, row,col){
	let obj = ''
	Object.keys(row).map(function(key, index) {
		if(row[key] !== null)
			if(typeof (row[key]['data']) !== 'undefined')
				if(typeof (row[key]['data']['id']) !== 'undefined')
					if(row[key]['data']['id'] === cell){
						obj = key
						return 0
					}
		return 0
	})
	let data = ''
	if(obj !== '') data = row[obj].data
	let value = ''
	if(data){
		let objectKey = data.type

		var show = 0;
		Object.keys(Param.APP[objectKey]).map(function(key,index){
			if(key === 'main_show') show = 1
			return 0
		})
		let attr = show === 1?Param.APP[objectKey].main_show:''
		value = data.attributes[attr]
	}
	// let user = row.user ? row.user : ''
	// let name = user ? user.attributes.name : ''
	return <span className="editable">{value}</span>
}


////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

class ItemLink extends React.Component {
	/*
		Single item in the tomany relationship formatter
	*/
	
	render(){
		let objectKey = this.props.item.type
		let attr = Param.APP[objectKey].main_show
                if(attr && this.props.item.attributes){
		    return <span>{this.props.item.attributes[attr]}</span>
                }
                return <span/>
	}
}

function toManyFormatter(cell, row, col){

	if(!cell || !cell.data){
		return <div/>
	}
	let items = ''
	try{
		items = cell.data.map(function(item){
						let item_data = item
						let result = '';
						if(item_data){
							result = <ItemLink item={item_data} />
						}
						return <div key={item_data.id}>{result}</div>
		})
	}
	catch(err){
		return <div>{JSON.stringify(cell.data)}</div>
}
	
	return <div>{items}</div>
}

class ToManyRelationshipEditor extends React.Component {
	/*
		props:
			row : values
			column: declaration
	*/
	constructor(props) {
	    super(props)

	    this.state = {
			selectedOption: ''
		}
		this.handleDelete.bind(this)
	}

	handleDelete(item_id){
		let items = []
		let rel_name = this.props.column.dataField
		for(let item of this.props.row[rel_name].data){
			if(item.id !== item_id){
				items.push(item)
			}
		}
		this.props.onUpdate(items)
	}

	// handleDelete(item_id){
	// 	this.props.onUpdate({'id':item_id,'action_type':'delete','url':this.props.column.relation_url})
	// }

	renderItem(item){
		let objectKey = item.type
		let attr = Param.APP[objectKey].main_show
		return <div key={item.id}>
					{item.attributes[attr]}
					<FontAwesomeIcon className="RelationDeleteIcon" icon={faTimes} onClick={() => this.handleDelete(item.id)}></FontAwesomeIcon>
				</div>
	}

 	render() {
		if(!this.props.column){
 			let error = 'ToManyRelationshipEditor: no column declaration'
 			//toastr.warning(error)
 			console.log(error, this.props)
 			return <div/>
 		}
		let rel_name = this.props.column.dataField
		if(!this.props.row || ! this.props.row[rel_name] || ! this.props.row[rel_name].data){
 			return <div/>
 		}
		let items = this.props.row[rel_name].data
		
	  	return <div>{items.map((item) => this.renderItem(item))}</div>
	}
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


function getOptions(collection,data){
	/*
		return an option list for the <Async> select filter
	*/
	let attr = Param.APP[collection].main_show

	var label = attr // attribute to be used for the label
	var offset = 0
	var limit = 20
		
	var result 
	if(Object.keys(data).length !== 0 && data[collection] !== undefined){
	// if(!data){
		result = (input,callback) => {
			let options = data[collection].map(function(item){ return { value: item.id, label: item.attributes[label]} } )

	  		//options.unshift({ value: null , label : 'No parent', style: { fontStyle: 'italic' } })
		    callback(null, {
		      options: options,
		      // CAREFUL! Only set this to true when there are no more options,
		      // or more specific queries will not be sent to the server.
		      complete: true
		    });
		}
	}else{
			result = (input, callback) => {
			let api_endpoint = ObjectApi.search(collection, { "query" : `${input}` }, offset, limit)
			api_endpoint.then((result) => {
				let options = result[collection].data.map(function(item){ return { value: item.id, label: item.attributes[label]} } )

				//options.unshift({ value: null , label : 'No parent', style: { fontStyle: 'italic' } })
				callback(null, {
				options: options,
				// CAREFUL! Only set this to true when there are no more options,
				// or more specific queries will not be sent to the server.
				complete: true
				});
			}, 500);
		}
	}

	return result
}


class toOneEditor extends React.Component {

	constructor(props) {
	    super(props);

	    this.state = {
			selectedOption: '',
			value:props.value
		}
	}

	onChange(selectedOption){
		
		if(!selectedOption){
			// filter has been cleared
			this.props.onUpdate(null)
			return
		}

		// this.parent.value = selectedOption.value
		// this.setState({ selectedOption : selectedOption});
		// selectedOption can be null when the `x` (close) button is clicked
		if (selectedOption) {
			let value = null // No parent id ==> remove the relationship 
			if(selectedOption.value){
				value = { id : selectedOption.value }
				this.setState({value : selectedOption.value})

				var sel_opt_rel_key = this.props.column.relationship
				
				for (let item of this.props.select_option[sel_opt_rel_key]) {
					if (item.id === selectedOption.value) {
						value = Object.assign({},{action_type:'one'}, {id:item.id}, {type:item.type}, {attributes:item.attributes})
						break;
					}
				}
			}
			this.props.onUpdate(value)
		}
	}

	/*getValue() {
		alert()
		return this.state.selectedOption.label
	}*/

	componentWillMount(){
		let key = this.props.column.relationship
		var offset = 0
		var limit = 20
		if(this.props.select_option === undefined || this.props.select_option[key] === undefined){
			this.props.action.updateSelectOptionAction(this.props.row.route, key,{ "query" : '' }, offset,limit)
			.then(()=>{
			})
		}
	}

 	render() {
		let key = this.props.column.relationship
	  	let options = getOptions(key,this.props.select_option)
		
	  	return <Select.Async
					// name="parentName"
				    // key="parent"
				    value={this.state.value}
				    // ref={ node => this.parent = node }
					loadOptions={options}
					// autoload
				    // onUpdate={onUpdate}
					onChange={this.onChange.bind(this)}
				    // filterOptions={(options, filter, currentValues) => {return options;}}
				    // { ...rest }
				/>
	  }
}

const mapStateToProps = (state,own_props) => ({
	select_option: state.object[own_props.row.route].select_option
})

const mapDispatchToProps = dispatch => ({
	action: bindActionCreators(ObjectAction, dispatch),
})

const connected_toOneEditor = connect(mapStateToProps,mapDispatchToProps)(toOneEditor)

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

let FormatterList = { cellFormatter : cellFormatter, 
					  toOneFormatter : toOneFormatter,
					  toManyFormatter: toManyFormatter,
					  toOneEditor: connected_toOneEditor,
					  ToManyRelationshipEditor: ToManyRelationshipEditor,
					  }

export default FormatterList


