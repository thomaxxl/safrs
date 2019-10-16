import React from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux'
import * as ModalAction from '../../action/ModalAction'
import BaseAction from './BaseAction'
import { Button, Modal, ModalHeader, ModalBody } from 'reactstrap'
import { Form, FormGroup, Label, Input } from 'reactstrap'
import Field from '../fields/Field';
import { faPlay } from '@fortawesome/fontawesome-free-solid'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import toastr from 'toastr'
import {APP} from '../../Config'

class CustomModal extends React.Component {    
    
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

    renderAttributes(){
        let data = this.props.formdata.attributes;
        return  <Form>
                    <FormGroup>
                    <Label for="id">ID</Label>
                    <Input value={this.props.selectedId} disabled={true}/>
                    </FormGroup>
                    {APP[this.props.objectKey].column.map(function(item,index){
                        return (<Field
                                    key={index}
                                    column={item} 
                                    disabled={true}
                                    value={ (data === undefined) 
                                    ? '' : data[item.dataField] }
                                />)
                    })}
                </Form>
    }

    render() {
        let attributes = this.renderAttributes();

        return (
            <Modal isOpen={this.props.modalview}  toggle={this.toggle} size="lg" >
                <ModalHeader toggle={this.toggle}>Custom</ModalHeader>
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

            let CustomModalWithConnect = connect(mapStateToProps, mapDispatchToProps)( CustomModal);

            var modal = <CustomModalWithConnect objectKey={this.props.objectKey} 
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
        return <Button color="none" onClick={this.onClick} >
                    <span><FontAwesomeIcon className="fa-fw" icon={faPlay}></FontAwesomeIcon>Custom</span>
                </Button>
    }   
}

export default CustomAction