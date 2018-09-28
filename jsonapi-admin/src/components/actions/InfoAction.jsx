import { faUserSecret  } from '@fortawesome/fontawesome-free-solid'
import React from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux'
import * as ModalAction from '../../action/ModalAction'
import BaseAction from './BaseAction'
import { Button, Modal, ModalHeader, ModalBody } from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import toastr from 'toastr'

class StatusModal extends React.Component {    
    
    constructor() {
        super()
        this.state = {
          modalview: true
        }
        this.toggle = this.toggle.bind(this);
    }

    toggle() {
        this.props.modalaction.getModalAction(false)
    }

    // getIncluded(){
    //     let included = this.props.formdata[this.props.objectKey].included
    // }

    getRelationships(rel_name){
        let result = []
        let relationships = this.props.formdata.relationships[rel_name]
        if(!relationships){
            return result
        }

    }

    renderAttributes(){
        let attributes = this.props.formdata.attributes;
        if (!this.props.selectedId || !attributes){
           return <div/>
        }

        return <div></div>
    }

    render() {
        let attributes = this.renderAttributes()
        return (
            <Modal isOpen={this.props.modalview}  toggle={this.toggle} size="lg" >
                <ModalHeader toggle={this.toggle}>Item Info</ModalHeader>
                <ModalBody>
                    {attributes}
                </ModalBody>
            </Modal>
        )
    }
}

class CustomAction extends BaseAction { 

    constructor(props){
        super(props)
        this.onClick = this.onClick.bind(this)
    }

    onClick(){
        let parent = this.props.parent;
        
        if(parent.state.selectedIds.length === 1)
        {
            parent.props.modalaction.getModalAction(true)
            parent.props.action.getSingleAction(parent.props.objectKey, parent.state.selectedIds[0]);
            
            const mapStateToProps = state => ({
                modalview: state.modalReducer.showmodal,
                formdata: state.selectedReducer,
            }); 
            const mapDispatchToProps = dispatch => ({
                modalaction: bindActionCreators(ModalAction,dispatch),
            })

            let StatusModalWithConnect = connect(mapStateToProps, mapDispatchToProps)( StatusModal);

            var modal = <StatusModalWithConnect objectKey={this.props.objectKey} 
                                selectedId={parent.state.selectedIds[0]} 
                                />
            parent.setState({modal: modal})
        }
        else if(parent.state.selectedIds.length > 1)
            toastr.error('More than two Items are Selected', '', {positionClass: "toast-top-center"});
        else {
            toastr.error('No Item Selected', '', {positionClass: "toast-top-center"});
        }
    }

    render(){
         return <Button className="c2-info" onClick={this.onClick} color="none"> 
                    <span><FontAwesomeIcon className="fa-fw" icon={faUserSecret}></FontAwesomeIcon> Status</span>
                </Button>
    }   
}

export default CustomAction