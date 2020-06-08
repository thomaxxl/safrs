import React from 'react';
import { Button } from 'reactstrap';
import BaseAction from './BaseAction'
import {connect} from 'react-redux'
import { bindActionCreators } from 'redux'
import { Modal, ModalHeader, ModalBody, ModalFooter } from 'reactstrap';
import Field from '../fields/Field';
import { Form } from 'reactstrap';
import {APP} from '../../Config.jsx'
import toastr from 'toastr'
import * as ObjectAction from '../../action/ObjectAction'
import * as ModalAction from '../../action/ModalAction'


class CreateModal extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            visible: true
        }
        this.toggle = this.toggle.bind(this)
        this.create = this.create.bind(this)

        this.show = this.show.bind(this)
        this.renderAttributes = this.renderAttributes.bind(this)
    }

    toggle() {
        this.props.modalaction.getModalAction(false)
    }

    create() {
        var post = {};
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
            .then(()=> this.props.action.getAction(this.props.objectKey, offset, limit) )
            .then(()=>{
                toastr.success('Saved', '', {positionClass: "toast-top-center"});
            });
    }

    show(){
        this.setState({
            visible: true
        })   
    }

    renderAttributes(){

        return <Form>
                    { APP[this.props.objectKey].column.map(function(column, index) {
                            if(column.readonly || column.relationship){
                                //return <div>{column.text}</div>
                                return <div/>
                            }
                            return (<Field 
                                    key={index} 
                                    column={column} 
                                    placeholder={column.placeholder}
                                    onChange={(event) => {
                                        this.setState({[column.dataField] : event.target.value})}}/>)
                        }, this)
                      }
                </Form>        
    }

    render() {
        let attributes = this.renderAttributes()

        return  <Modal isOpen={this.props.modalview} toggle={this.toggle} className={this.props.className}>
                    <ModalHeader toggle={this.toggle}>Create {this.props.objectKey} Item</ModalHeader>
                    <ModalBody>
                        {attributes}
                    </ModalBody>
                    <ModalFooter>
                        <Button color="primary" onClick={this.create}>Create</Button>
                        <Button color="secondary" onClick={this.toggle}>Cancel</Button>
                    </ModalFooter>
                </Modal>
    }
}

class CreateAction extends BaseAction {
    // constructor(props){
    //     super(props)
    // }

    onClick(){

        let parent = this.props.parent;
        parent.props.modalaction.getModalAction(true)//JJW
        
        const mapStateToProps = state => ({
            modalview: state.modalReducer.showmodal,
            datas: state.object
        }); 
        const mapDispatchToProps = dispatch => ({
            action: bindActionCreators(ObjectAction, dispatch),
            modalaction: bindActionCreators(ModalAction,dispatch),
        });
        let CreateModalWithConnect = connect(mapStateToProps, mapDispatchToProps)( CreateModal);

        var modal = <CreateModalWithConnect objectKey={this.props.objectKey}  props={parent}/>
        parent.setState({modal: modal})
    }

    render(){
        
        return <Button color="none"
                    onClick={this.onClick}
                >
                    <i className="fa fa-plus" aria-hidden="true"/> New
                </Button>
    }
}

export default CreateAction;