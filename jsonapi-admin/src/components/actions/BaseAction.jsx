import React from 'react';
import { Button } from 'reactstrap';

class BaseAction extends React.Component {
    constructor(props){
        super(props)
        this.onClick = this.onClick.bind(this)
    }

    onClick(){
        alert();
    }

    render(){
        return <Button color = "primary"
                    onClick={this.onClick}
                >
                    <i className="fa fa-plus" aria-hidden="true"/> Dummy
                </Button>
    }
}

export default BaseAction;