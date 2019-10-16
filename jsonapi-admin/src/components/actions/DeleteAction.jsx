import React from 'react';
import { connect } from 'react-redux'
import { Button } from 'reactstrap';
import BaseAction from './BaseAction'
import toastr from 'toastr';
import { faTrashAlt  } from '@fortawesome/fontawesome-free-solid'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'


class DeleteAction extends BaseAction{  
    // constructor(){
    //     super()
    // }

    onClick(){
        let parent = this.props.parent
        parent.setState({ModalTitle: 'Delete'});
        if(parent.state.selectedIds.length !== 0){
            if (!window.confirm("Do you want to delete selected items?"))  return;
            
            var offset = this.props.datas[this.props.objectKey].offset;
            var limit = this.props.datas[this.props.objectKey].limit;
            parent.props.action.deleteAction(parent.props.objectKey, parent.state.selectedIds, offset, limit)
                .then(()=>{
                    toastr.info('Deleted', '', {positionClass: "toast-top-center"});
                });
                parent.state.selectedIds = [];
        }
    }

    render(){
        return <Button color = "none"
                    onClick={this.onClick}
                >
                    <FontAwesomeIcon icon={faTrashAlt}></FontAwesomeIcon> Delete
                </Button>
    }
}

const mapStateToProps = state => ({
    datas: state.object
}); 
export default connect(mapStateToProps)( DeleteAction);