/*
    The ApiObjectContainer renders the action buttons and the [List](Common/List.jsx) Component which renders the react-bootstrap-table
    Each row in the table corresponds to an backend jsonapi/database item
*/
import React from 'react';
import toastr from 'toastr';
import { withRouter } from 'react-router'
import { Row, Col } from 'reactstrap';
import List from '../Common/List';
import {APP, ActionList} from '../../Config.jsx';
import { Input } from 'reactstrap'
import { get_ApiObject } from '../../api/ApiObject';
import './style.css'
// const DEFAULT_PAGE_SIZE = 50
// const DEFAULT_PAGE_OFFSET = 0
const WAIT_INTERVAL = 1200; // Timeout for the search
const ENTER_KEY = 13;
const toasterPosition =  {positionClass: "toast-bottom-right"}

class ApiObjectContainer extends React.Component {
    /*
        Container for the react-bootstrap-table and related components
    */

    constructor(props) {
        /*
            This component should've been constructed with the "connected" props, eg.
                    objectKey: The jsonapi collection key
                    item: APP configuration item (from Config.jsx/Config.json)
                    api_data: holds the list of data that will be displayed in the react-bootstrap-table
                    inputflag: 
                    action: 
                    modalaction:
                    inputaction: 
                    spinnerAction: 

            the actual table is rendered in the List component
        */
        super(props)
        this.state = {
            selectedIds: [], // The ids of the items selected by the checkboxes
            modal : null, // if a modal is shown, it will be kept here. TODO: we shouldn't keep components in the state
        }
        this.handleSearch = this.handleSearch.bind(this)
        this.getAction = this.getAction.bind(this)
        this.actions = {}
    }
    
    getAction(...extraArgs){
        /*
            Retrieve the data from the api
        */
        let config  = APP[this.props.objectKey]
        let request_args = config.request_args ? config.request_args : {}
        if(!extraArgs || extraArgs.length == 0){
            console.warn('no extraArgs')
            var key = this.props.objectKey
            extraArgs = [this.props.api_data[key].offset, this.props.api_data[key].limit]
        }

        let getArgs = [ this.props.objectKey, extraArgs[0],extraArgs[1], request_args]
        return this.props.action.getAction(...getArgs)
    }

    handleRowSelect(itemData, state, index) {
        /*
            handler for when the user selected a row with the checkbox
            => add/remove the row id to/from selectedIds
        */
        var orgIndex = this.state.selectedIds.indexOf(itemData.id);

        if (state && orgIndex === -1){
            this.state.selectedIds.push(itemData.id)
        }
        else if (!state && orgIndex !== -1){
            this.state.selectedIds.splice(orgIndex, 1)
        }
    }

    componentDidMount() {
        /*  
            Retrieve the data from the api
            this.props.router.setRouteLeaveHook(this.props.route, this.routerWillLeave)
        */
        var key = this.props.objectKey
        if(this.props.spinnerAction){
           this.props.spinnerAction.getSpinnerStart()
        }
        // var self = this;
        // var timer_flag = 1;
        this.getAction(
            this.props.api_data[key].offset,
            this.props.api_data[key].limit)
            .then(rlt=>{
                if(this.props.spinnerAction){
                    this.props.spinnerAction.getSpinnerEnd()
                }
                // this.timer = setInterval(function() {
                //     console.log(self.props.objectKey)
                //     var key = self.props.objectKey
                //     if(timer_flag){
                //         timer_flag =  0
                //         self.props.action.getAction(key, self.props.api_data[key].offset, self.props.api_data[key].limit)
                //         .then(()=>{
                //             timer_flag = 1;
                //         })
                //         .catch(error => {
                //             alert('Invalid back-end-url.Please insert valid url again');
                //             clearInterval(this.timer);
                //             self.props.history.push('/');
                //         })
                //     }
                // }, Param.Timing);
            })
            .catch(error => {
                toastr.error('Failed to retrieve data from back-end. Verify your configuration.','', { timeOut: 0 });   
                clearInterval(this.timer);
		console.error(error)
                //this.props.history.push('/');
            })
    }

    componentWillUnmount() {  
        clearInterval(this.timer);
        this.props.inputaction.getInputAction(true);
    }

    onTableChange(page,sizePerPage){
        var newOffset = (page-1) * sizePerPage
        this.getAction(newOffset,sizePerPage);
    }

    getSelectedItems(){
        /*
            Return all selected items
        */
        if(this.state.selectedIds.length === 0){
            toastr.error('No item selected', '', toasterPosition)
            return null
        }

        let items = this.props.api_data[this.props.objectKey].data
        var selItems = [];
        for (var item of items) {
            if(this.state.selectedIds.indexOf(item.id) >= 0) {
                selItems.push(item);
            }
        }
        if (selItems.length === 0){
            toastr.error('Item not found', '', toasterPosition)
        }
        return selItems;
    }

    getSelectedItem(){
        /*
            Return one selected item, error if more
        */
        let selectedItems = this.getSelectedItems()
        if(!selectedItems){
            return {} // error already shown in getSelectedItems
        }
        if(selectedItems.length > 1){
            toastr.error('To many items selected')
        }
        return selectedItems[0]
    }


    renderAction(action_name){
        /*
            Render the action (button) specified in the Config.json
            The action should be mapped in the Param.ActionList
        */
        const Action = ActionList[action_name]
        if(!Action){
            console.log(`Invalid Action ${action_name}`)
            return <div/>
        }
        
        const action = <Action key={action_name}
                               onClick={()=>alert()}
                               selectedIds={this.state.selectedIds}
                               objectKey={this.props.objectKey}
                               parent={this} />
        this.actions[action_name] = action
        return action
    }

    handleSearch(value){
        /*
            onChange handler for the searchbar Input:
            - set the search parameter in the redux store
            - refresh the api_objects
        */
        if(this.props.spinnerAction){
           this.props.spinnerAction.getSpinnerStart()
        }
        this.props.api_data[this.props.objectKey].search = value
        this.getAction().then(()=>{if(this.props.spinnerAction){this.props.spinnerAction.getSpinnerEnd()}})
    }

    handleSave(column,dataField){
        /*
            Save a modified row => call this.props.action.saveAction for this api object
        */
        console.debug('handleSave', column, dataField)
        var key = this.props.objectKey
        let saveArgs = [ this.props.objectKey, column, this.props.api_data[key].offset,  this.props.api_data[key].limit, dataField]
        return this.props.action.saveAction(...saveArgs).catch(error => {
                toastr.error(error, '', toasterPosition)
            })
            .then(get_ApiObject(key, column.id))
            .then(toastr.success('saved', '', toasterPosition))
            /*.then(this.getAction(this.props.api_data[key].offset,
                                 this.props.api_data[key].limit))*/
            
    }

    handleSaveRelationship(newValue, row, column){
        /*
            Save the modified relationship
        */
        var key = this.props.objectKey
        let rel_name = column.relation_url
        let relArgs = [this.props.objectKey, row.id, rel_name, newValue, this.props.api_data[key].offset, this.props.api_data[key].limit]
        console.log('handleSaveRelationship', newValue)
        this.props.action.updateRelationshipAction(...relArgs)
        .then((e) => console.log(e))
        .catch(error => {
                toastr.error(error, '', toasterPosition)
            })
        .then(toastr.success('Saved', '', toasterPosition))

            //.then(this.getAction())
    }

    render() {
        if(this.props.item.container){
            const Container = this.props.item.container
            return <Container data={this.props.api_data[this.props.objectKey]}
                              onChange={this.handleSearch}
                              search={this.props.api_data[this.props.objectKey].search} />
        }
        return (
            <div className="container-fluid">
                <Row>
                    <Col sm={8}>
                        <div className="btn-group" role="group">
                            {this.props.item.actions.map((action_name) => 
                                this.renderAction(action_name)
                            )}
                        </div>
                    </Col>
                    <Col sm={4}>
                        <SearchInput onChange={this.handleSearch} search={this.props.api_data[this.props.objectKey].search}/>
                    </Col>
                </Row>

                <Row>
                    <Col sm={12}>
                        <List data={this.props.api_data[this.props.objectKey]} 
                              actions={this.actions}
                              objectKey={this.props.objectKey}
                              handleRowSelect={this.handleRowSelect.bind(this)} 
                              columns={this.props.item.column}
                              selectedIds={this.state.selectedIds}
                              filter={this.props.api_data[this.props.objectKey].filter}
                              onChange={this.handleSearch.bind(this)}
                              handleSave={this.handleSave.bind(this)}
                              handleSaveRelationship={this.handleSaveRelationship.bind(this)}
                              location={this.props.location}
                              table={this}
                              getAction={this.getAction.bind(this)}
                              onTableChange={this.onTableChange.bind(this)}/>
                    </Col>
                </Row>
                <ModalContainer modal={this.state.modal} />
            </div>
        )
    }
}

class ModalContainer extends React.Component {
    render(){
        return <div>{this.props.modal}</div>
    }
}


class SearchInput extends React.Component {
    /*
        The search bar rendered on top of the table,
        changes will trigger handleSearch (check the ApiObjectContainer.handleSearch)
    */
    constructor(props) {
        super();
        this.state = {
            value: props.value
        }
        this.triggerChange = this.triggerChange.bind(this)
        
    }

    componentWillMount() {
        this.timer = null;
    }

    handleChange(event) {
        let value = event.target.value
        clearTimeout(this.timer);
        this.setState({ value });
        // Wait "WAIT_INTERVAL" ms, then perform the search
        this.timer = setTimeout(this.triggerChange, WAIT_INTERVAL);
    }

    handleKeyDown(e) {
        if (e.keyCode === ENTER_KEY) {
            this.triggerChange()
        }
    }

    triggerChange() {
        const { value } = this.state;
        this.props.onChange(value);
    }

    render() {
        
        return (
            <Input
                className="search"
                placeholder="search"
                onChange={this.handleChange.bind(this)}
                onKeyDown={this.handleKeyDown.bind(this)}
            />
        );
    }
}

export default withRouter(ApiObjectContainer)
