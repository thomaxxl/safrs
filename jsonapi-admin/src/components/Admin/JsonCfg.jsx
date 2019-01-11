import React from 'react';
import toastr from 'toastr';
import { 
  TextArea, 
  Form
} from 'semantic-ui-react'
import 'semantic-ui-css/semantic.min.css'
import 'bootstrap/dist/css/bootstrap.min.css'
import './Admin.css'
import {
  Button,
} from 'reactstrap';
import * as Param from '../../Config'


class JSONCfg extends React.Component{

  constructor(props) {
    super(props)
    this.state = {
       app_string : JSON.stringify(Param.APP,null,2)
    }
  }

  handleOnchange(e) {
    this.setState({app_string : e.target.value })
  }

  
  updateConfig(){
    let APP
    try{
        APP = JSON.parse(this.state.app_string)
    }
    catch(err){
        toastr.error('Failed to parse JSON')
        return
    }
    toastr.info('Updated Config')
    localStorage.setItem('json', this.state.app_string)
    Object.assign(Param.APP, APP)
}

  render(){
    return  <Form>
              <h3>Configuration JSON</h3>
              <Button onClick={this.updateConfig.bind(this)}>Update</Button>
              <TextArea onChange={this.handleOnchange.bind(this)} autoHeight value={this.state.app_string} />
            </Form>
  }
}


export {JSONCfg}