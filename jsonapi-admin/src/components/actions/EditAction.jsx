import React from 'react';
import { Button } from 'reactstrap';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux'
import BaseAction from './BaseAction'
import { Modal, ModalHeader, ModalBody, ModalFooter } from 'reactstrap';
import Field from '../fields/Field';
import { Form } from 'reactstrap';
import { APP } from '../../Config.jsx'
import toastr from 'toastr'
import { faPencilAlt  } from '@fortawesome/fontawesome-free-solid'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import * as ObjectAction from '../../action/ObjectAction'
import * as ModalAction from '../../action/ModalAction'

class EditModal extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            visible: true
        }
        this.toggle = this.toggle.bind(this)
        this.show = this.show.bind(this)
        this.submit = this.submit.bind(this)
        this.renderAttributes = this.renderAttributes.bind(this)
    }

    toggle() {
        this.props.modalaction.getModalAction(false)
    }

    show(){
        this.setState({
            visible: true
        })   
    }

    submit() {
        
        var post = {};
        post.id = this.props.selectedId;
        APP[this.props.objectKey].column.map(function(item, index) {
            if(item.dataField && this.state[item.dataField] !== undefined){
                post[item.dataField] = this.state[item.dataField]
            }
            return 0;
        }, this);
        this.props.modalaction.getModalAction(false)

        var offset = this.props.datas[this.props.objectKey].offset;
        var limit = this.props.datas[this.props.objectKey].limit;
        
        this.props.action.saveAction(this.props.objectKey, post, offset, limit)
            .then(()=>{
                toastr.success('Saved', '', {positionClass: "toast-top-center"});
            });
    }

    renderAttributes(){
        let data = this.props.formdata.attributes
        console.log(APP)
        return <Form>
                    { APP[this.props.objectKey].column.map(function(item, index) {
                            if( !data || item.dataField === undefined ){
                                return <div key={index} />
                            }
                            let value = (data === undefined || data[item.dataField] === "") ? item.placeholder : data[item.dataField]
                          
                            return (<Field 
                                    row={data}
                                    key={index}
                                    data={data}
                                    column={item}
                                    // value={this.state[item.dataField] === undefined ? '':this.state[item.dataField]}
                                    placeholder={value}
                                    onChange={(event) => {
                                            if(event && event.target){
                                                this.setState({[item.dataField] : event.target.value})
                                            }
                                        }
                                    }/>)
                        }, this)
                      }
                </Form>        
    }

    render() {

        let attributes = this.renderAttributes()

        return  <Modal isOpen={this.props.modalview} toggle={this.toggle} className={this.props.className}>
                    <ModalHeader toggle={this.toggle}>Edit </ModalHeader>
                    <ModalBody>
                        {attributes}
                    </ModalBody>
                    <ModalFooter>
                        <Button color="primary" onClick={this.submit}>Save</Button>
                        <Button color="secondary" onClick={this.toggle}>Cancel</Button>
                    </ModalFooter>
                </Modal>
    }
}


class EditAction extends BaseAction {  
    
    // constructor(props){
    //     super(props)
    // }

    onClick(){  

        let parent = this.props.parent;
        
        if(parent.state.selectedIds.length === 1)
        {
            parent.props.modalaction.getModalAction(true)
            parent.props.action.getSingleAction(parent.props.objectKey, parent.state.selectedIds[0]);
            
            const mapStateToProps = state => ({
                modalview: state.modalReducer.showmodal,
                formdata: state.selectedReducer,
                datas: state.object
            }); 
            const mapDispatchToProps = dispatch => ({
                action: bindActionCreators(ObjectAction, dispatch),
                modalaction: bindActionCreators(ModalAction,dispatch),
            })

            let EditModalWithConnect = connect(mapStateToProps, mapDispatchToProps)(EditModal);

            var modal = <EditModalWithConnect objectKey={this.props.objectKey} 
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
        return <Button color = "none"
                    onClick={this.onClick}           
                >
                    <FontAwesomeIcon icon={faPencilAlt}></FontAwesomeIcon> Edit
                </Button>
    }
}

export default EditAction;