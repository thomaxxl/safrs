import React from 'react';
import { connect } from 'react-redux'
import { bindActionCreators } from 'redux'
import * as InputAction from '../action/InputAction'
import * as Param from '../Config'
import { Link } from 'react-router-dom'
import {
    TextArea, Button, Form, Tab
  } from 'semantic-ui-react'
import toastr from 'toastr';
import {AdminTab} from './Admin/Admin'
import 'semantic-ui-css/semantic.min.css'
import {TestCfg} from './Admin/Tests'
import {JSONCfg} from './Admin/JsonCfg'
import {InputGroup,
    InputGroupAddon,
    Input } from 'reactstrap';
  
import Cookies from 'universal-cookie';
  
class Home extends React.Component {

    render(){

      const panes = [
        { menuItem: 'Home', render: () => <Tab.Pane><HomeTab {...this.props}/></Tab.Pane> },
        { menuItem: 'Config', render: () => <Tab.Pane><AdminTab {...this.props}/></Tab.Pane> },
        { menuItem: 'JSON', render: () => <Tab.Pane><JSONCfg/></Tab.Pane> },
        { menuItem: 'Tests', render: () => <Tab.Pane><TestCfg></TestCfg></Tab.Pane> },
      ]
      
      return <Tab panes={panes} defaultActiveIndex={0} />
      /*return <div>
                <header>
                    <div className="jumbotron jumbotron-fluid bg-info text-white text-center">
                        <div className="container">
                            <h1 className="display-4">jsonapi-admin UI</h1>
                            React+redux js frontend for a jsonapi backend
                        </div>
                    </div>
                </header>
            </div>*/
    }
}


class HomeTab extends React.Component {
    constructor(props) {
         super(props)
         this.state = {
            app_string : JSON.stringify(Param.APP,null,2)
         }
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

    handleOnchange(e) {
        this.setState({app_string : e.target.value })
    }

    change_url(e){
        let api_url = e.target.value
        this.props.inputaction.getUrlAction(e.target.value);
        localStorage.setItem('url',api_url);
        const cookies = new Cookies()
        cookies.set('api_url', api_url)
        console.log('url changed')
    }

    render(){

        const url_input=  <InputGroup className="Left">
                            <InputGroupAddon addonType="prepend">Json:API Root URL</InputGroupAddon>
                                <Input  value={this.props.inputflag.url===''?Param.URL:this.props.inputflag.url} 
                                        onChange={this.change_url.bind(this)} 
                                        placeholder="Root URL"/>
                          </InputGroup>
        return (<div className="container">
                    <ul>
                    <li>{url_input}</li>
                    <li>
                            <a href="https://github.com/thomaxxl/jsonapi-admin">Github</a>
                        </li>
                        <li>This webapp implements CRUD operations on the jsonapi at <a href={this.props.inputflag.url}>{this.props.inputflag.url}</a>. The interface is generated from the swagger configuration (json) of <a href={this.props.inputflag.url}>{this.props.inputflag.url}</a> </li>
                        <li>UI Configuration ( Genrated by the <Link to={ {pathname: "/Admin"} } >admin interface)</Link> ):
                        <br/>
                            
                          <Button onClick={this.updateConfig.bind(this)}>Update</Button>
                            <Form><TextArea onChange={this.handleOnchange.bind(this)} autoHeight value={this.state.app_string} /></Form>
                        </li>
                    </ul>
                </div>
        );
    }
};

const mapStateToProps = state => ({
    inputflag: state.inputReducer
})

const mapDispatchToProps = dispatch => ({
    inputaction: bindActionCreators(InputAction,dispatch),
})
  
// let exported = Param.Home ? Param.Home : Home
let exported = Home


export default connect(mapStateToProps,mapDispatchToProps)(exported);
