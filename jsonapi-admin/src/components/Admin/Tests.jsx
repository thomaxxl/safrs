import React from 'react';
import {
    TextArea, Button, Form, Tab, Input
  } from 'semantic-ui-react'

import * as Param from '../../Config'
import { Col } from 'reactstrap';

class TestCfg extends React.Component {

    constructor(props){
        super(props)
        this.state = { }
    }

    testAll(){
        alert()
    }

    render(){

        let collections = []
        Object.keys(Param.APP).map(function(key) {
            collections.push(<TestCollection key={key} name={key}/>)
        })
    
        return <div>
                    <Button onClick={this.testAll.bind(this)} color="blue">Read Samples</Button>
                    <Button onClick={this.testAll.bind(this)} color="green">Test Everything</Button>
                    {collections} 
               </div>
    }
}

class TestCollection extends React.Component{

    constructor(props){
        super(props)
        this.state = { id : '' }
    }

    testCreate(){

    }

    testRead(){

    }
    
    testUpdate(){

    }
    
    testDelete(){

    }

    handleChange = (e, { name, value }) => this.setState({ [name]: value })

    render(){
        const config = Param.APP[this.props.name]
        const columns = config.column.map(col => <TestColumn key={col.text} {...col} /> )
        let id = this.state.id

        return <Form>
                <h3>{this.props.name}</h3>
                <Button color="olive" onClick={this.testCreate.bind(this)}>Create</Button>
                <Button color="blue" onClick={this.testCreate.bind(this)}>Read</Button>
                <Button color="teal" onClick={this.testCreate.bind(this)}>Update</Button>
                <Button color="red" onClick={this.testCreate.bind(this)}>Delete</Button>
                <Form.Group inline  widths='equal'>
                <Form.Field>
                    <label>ID</label>
                    <Input placeholder='' />
                </Form.Field>
                {columns}
                </Form.Group>
               </Form>
    }
}

class TestColumn extends React.Component{

    render(){
        return <Form.Field>
                    <label>{this.props.text}</label>
                    <Input fluid placeholder='' />
                </Form.Field>
        
    }
}

class TestCreate extends React.Component{

    render(){
        return <div><h3>{this.props.name}</h3></div>
    }
}

class TestUpdate extends React.Component{

    render(){
        return <div><h3>{this.props.name}</h3></div>
    }
}

class TestDelete extends React.Component{

    render(){
        return <div><h3>{this.props.name}</h3></div>
    }
}


//

class TestCreateRelationship extends React.Component{

    render(){
        return <div><h3>{this.props.name}</h3></div>
    }
}

class TestUpdateRelationship extends React.Component{

    render(){
        return <div><h3>{this.props.name}</h3></div>
    }
}

class TestDeleteRelationship extends React.Component{

    render(){
        return <div><h3>{this.props.name}</h3></div>
    }
}

export {TestCfg}