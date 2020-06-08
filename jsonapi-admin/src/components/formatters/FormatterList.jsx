import React from 'react'
import { faPlus, faTimes } from '@fortawesome/fontawesome-free-solid'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
// import toastr from 'toastr'
import {APP} from '../../Config.jsx';
import Select from 'react-select'
import { Async } from 'react-select';
import 'react-select/dist/react-select.css';
import ObjectApi from '../../api/ObjectApi'
import { connect } from 'react-redux'
import { bindActionCreators } from 'redux'
import * as ObjectAction from '../../action/ObjectAction'
import { get_ApiObject, get_ApiComponent } from '../../api/ApiObject';

function cellFormatter(cell, row) {

    return <strong><div className="call">{ cell }</div></strong>
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

function type2collection(type){
	for(let key of Object.keys(APP)){
	        if(APP[key].API_TYPE == type){
	            return key
	        }
	    }
}

function toOneFormatter_(cell, row, col){
	let obj = ''
	Object.keys(row).map(function(key, index) {
		if(row[key] !== null)
			if(typeof (row[key]['data']) !== 'undefined' && row[key]['data'])
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
	const type = row.type

	if(data){
		let objectKey
		for(let key of Object.keys(APP)){
	        if(APP[key].API_TYPE == type){
	            objectKey = key
	        }
	    }
	    if(!objectKey){
	    	console.warn("Invalid type")
	    	return <div/>
	    }
		var show = 0;
		Object.keys(APP[objectKey]).map(function(key,index){
			if(key === 'main_show') show = 1
			return 0
		})
		let attr = show === 1?APP[objectKey].main_show:''
		value = data.attributes[attr]
	}
	// let user = row.user ? row.user : ''
	// let name = user ? user.attributes.name : ''
	
	return <span className="editable">{value?value:cell}</span>
}


////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

class ItemLink extends React.Component {
	/*
		Single item in the tomany relationship formatter
	*/
	
	render(){
		let objectKey = type2collection(this.props.item.type)
		let attr = APP[objectKey].main_show
		return <span>{this.props.item.attributes[attr]}</span>
	}
}

function toManyFormatter(cell, row, col){

	if(!cell || !cell.data){
		return <div/>
	}

	const items = cell.data.map(function(item){
					console.log('item',item)
					let item_data = item
					let result = '';
					if(item_data){
						result = <ItemLink item={item_data} />
					}
					return <div key={item_data.id}>{result}</div>
	})
	
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
	    console.log('ToManyRelationshipEditor')
	    console.log(props)
	    this.state = {
			selectedOption: '',
			show_add_rel : false
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
	// 	console.log('track_many_edotor_1')
	// 	console.log(this.props)
	// 	this.props.onUpdate({'id':item_id,'action_type':'delete','url':this.props.column.relation_url})
	// }

	renderItem(item){
		let object_cfg;
		for(var k in APP){
			if(APP[k].API_TYPE == item.type){
				object_cfg = APP[k]
			}
		}
		let attr = object_cfg && object_cfg.main_show
		if(!attr){
			console.log()
			console.log(item)
			return <div/>
		}
		if(!attr && object_cfg['column']){
			//APP[objectKey]['column'][0]['dataField']
		}
		return <div key={item.id}>
					{item.attributes[attr]}
					<FontAwesomeIcon className="RelationDeleteIcon" icon={faTimes} onClick={() => this.handleDelete(item.id)}></FontAwesomeIcon>
				</div>
	}
	
	toggle_add_rel(){
		this.setState({ show_add_rel : ! this.state.show_add_rel})
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
		const select = this.state.show_add_rel ? 
				<Select value={''} loadOptions={{}} onChange={alert} /> : 
				<FontAwesomeIcon className="RelationAddIcon" icon={faPlus} onClick={this.toggle_add_rel.bind(this)}/>
		const Editor = connected_toOneEditor
	  	return <div>
	  				{items.map((item) => this.renderItem(item))}
	  				
	  				{select}
	  			</div>
	}
}


////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


function getOptions(collection, data, queryArgs) {
    /*
		return an option list for the <Async> select filter
	*/
    if (!APP[collection]) {
        console.log('Invalid Collection');
        return {};
    }
    if(!queryArgs){
        queryArgs = {}
    }
    let attr = APP[collection].main_show;

    var label = attr; // attribute to be used for the label
    var offset = 0;
    var limit = 8;

    var result;
    if (Object.keys(data).length !== 0 && data[collection] !== undefined) {
        // if(!data){
        result = (input, callback) => {
            let options = data[collection].map(function(item) {
                return { value: item.id, label: item.attributes[label] };
            });

            //options.unshift({ value: null , label : 'No parent', style: { fontStyle: 'italic' } })
            callback(null, {
                options: options,
                // CAREFUL! Only set this to true when there are no more options,
                // or more specific queries will not be sent to the server.
                complete: true
            });
        };
    } else {
        // SEARCH
        result = (input, callback) => {
            let api_endpoint = ObjectApi.search(
                collection,
                { query: `${input}` },
                offset,
                limit,
                queryArgs
            );
            api_endpoint.then(result => {
                let options = result[collection].data.map(function(item) {
                    return { value: item.id, label: item.attributes[label] };
                });

                //options.unshift({ value: null , label : 'No parent', style: { fontStyle: 'italic' } })
                callback(null, {
                    options: options,
                    // CAREFUL! Only set this to true when there are no more options,
                    // or more specific queries will not be sent to the server.
                    complete: true
                });
            }, 500);
        };
    }

    return result;
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
				console.log(this.props.column)
				console.log(this.props.select_option)
				
				for (let item of this.props.select_option[sel_opt_rel_key] || []) {
					if (item.id === selectedOption.value) {
						value = Object.assign({},{action_type:'one'}, {id:item.id}, {type:item.type}, {attributes:item.attributes})
						break;
					}
				}
				if(!value.type){
					alert("Invalid type "+sel_opt_rel_key)
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
		/*if(this.props.select_option === undefined || this.props.select_option[key] === undefined){
			this.props.action.updateSelectOptionAction(this.props.row.route, key,{ "query" : '' }, offset,limit)
			.then(()=>{
			})
		}*/
	}

	addItem(item) {
        // add(=> jsonapi patch) the case to the case/image relationship
        /*
         */
         if(!item){
            return;
         }
        const source_id = this.props.row.id;
        const item_id = item.id;
        const item_name = item.name;
        const target = { id: item_id, type: 'Publishers' };
        const rel_name = this.props.column.dataField;
        let items = this.props.row[rel_name].data || [];
        items.push(target);
        this.props.onUpdate(items);
        
    }

 	render() {
	 	return <div>todo</div>

		let key = this.props.column.relationship || this.props.column.relationship_type
		if(!key){
			console.log(this.props.column)
			console.log(this.props.column.relationship)
			alert('no relationship key in config', this.props.column)
			return <div/>
		}
		const rel_name = this.props.column.dataField;
        if (!this.props.row || !this.props.row[rel_name]) {
            console.log('rd:', rel_name, this.props.row);
            return <div />;
        }
		const items = this.props.row[rel_name].data || [];
	  	let options = getOptions(key,this.props.select_option)
	  	const loadOptions = getOptions('Publishers', {});
	  	const { value, onUpdate, ...rest } = this.props;
		const async = (
            <Async
                name="caseName"
                key="case"
                value={value}
                ref={node => (this.image_ref = node)}
                loadOptions={loadOptions}
                onUpdate={onUpdate}
                onChange={this.addImage.bind(this)}
                filterOptions={(options, filter, currentValues) => {
                    return options;
                }}
                {...rest}
            />
        );
	  	return (
            <div>
                {items.map(item => this.renderItem(item))}
                {async}
            </div>
        );
	  }
}


function toOneFormatterFactory(collection){

	function toOneFormatter(cell, row) {
	    if (
	        !row ||
	        !row.included ||
	        !row.relationships ||
	        !row.relationships.reader ||
	        !row.relationships.reader.data
	    ) {
	        console.warn(row)
	        return <div >+</div>;
	    }
	    const reader = get_ApiComponent(collection, cell, "todo");
	    return <div>{reader}</div>
	}
	return toOneFormatter
}

const reviewReaderFormatter = toOneFormatterFactory("People")


const mapStateToProps = (state, own_props) => { 

	let select_option;
	if(own_props.row && own_props.row.route){
		select_option = state.object[own_props.row.route].select_option
	}
	else{
		alert('error')
	}

	return { select_option: select_option} 
}

const mapDispatchToProps = dispatch => ({
	action: bindActionCreators(ObjectAction, dispatch),
})

const connected_toOneEditor = connect(mapStateToProps, mapDispatchToProps)(toOneEditor)

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

let FormatterList = { cellFormatter : cellFormatter,
					  toManyFormatter: toManyFormatter,
					  toOneEditor: connected_toOneEditor,
					  ToManyEditor: ToManyRelationshipEditor,
					  ToManyRelationshipEditor: ToManyRelationshipEditor,
					  reviewReaderFormatter : reviewReaderFormatter,
					}

export {FormatterList, toOneFormatterFactory}
