import React from 'react';
import { Button, Modal, ModalHeader, ModalBody, ModalFooter, Col } from 'reactstrap';
import { Form, FormGroup, Label, Input } from 'reactstrap';
import toastr from 'toastr'
import {Config, api_config} from '../../Config.jsx';
import Cookies from 'universal-cookie';
import './login_style.css'
import ReactTooltip from 'react-tooltip';

class LoginModal extends React.Component {
  constructor(props) {
    super(props)
    const cookies = new Cookies()
    var token = cookies.get('token')
    var username = cookies.get('username')

    this.state = {
      modal: props.logged_in,
      username : username ? username : 'automat',
      password : '',
      token : token
    };
    this.portalId = 'login_form'
    this.toggle = this.toggle.bind(this)
  }

  componentDidMount() {

  }

  componentWillUnmount() {
    //document.body.removeChild(this.portalElement);
  }

  componentDidUpdate() {
    //React.render(<div {...this.props}>FFFFFFFFFF{this.props.children}</div>, this.portalElement);
  }

  toggle() {
    this.setState({
      modal: !this.state.modal
    })
  }

  login(){
    // authenticate in common.jsx
    if(Config.authenticate){
        Config.authenticate(api_config.baseUrl, this.state.username, this.state.password)
          .then(this.toggle())
    }
  }

  logout(){
      // authenticate in common.jsx
      Config.authenticate(api_config.baseUrl, null) // call without args to logoff
      document.location.href = Config.logout_url
  }

  updateInputValue(evt) {
    let s = {}
    s[evt.target.name] = evt.target.value
    this.setState(s);
  }

  logged_in(){
      const cookies = new Cookies();
      return cookies.get('token') && this.state.token && this.state.token !== 'false' 
  }

  handleKeyPress(event){
    // default submit doesn't work, possibly due to reactstrap version, dirty hack below
    if(event.key == 'Enter'){
      this.login()
    }
  }

  render() {

    const cookies = new Cookies()
    var username = cookies.get('username')

    var link
    var isOpen = false
    if(this.logged_in()){
        link  = <span id="login" onClick={this.logout.bind(this)} data-for="headertt" data-tip={`log out ${username} `}>Logout</span>
    }
    else {
        link = <span id="login" onClick={this.toggle}>{this.props.logged_in ? 'Logout' : 'Login' }</span>
        isOpen = true
    }

    const login_background = isOpen? <div id="login_background" /> : <div/>
    const externalCloseBtn = <button className="close" style={{ position: 'absolute', top: '15px', right: '15px' }} onClick={this.toggle}>&times;</button>;

    return (
      <div>
        {link}
        {login_background}
        <Modal id="login-modal" isOpen={isOpen} toggle={this.toggle} className={this.props.className} external={externalCloseBtn} contentClassName="login-content">
          <ModalBody>
            <Form onKeyPress={this.handleKeyPress.bind(this)}>
              <FormGroup row>
                  <Label className="login-label" for="username" sm={2}>Username</Label>
                  <Col sm={10}>
                    <Input name="username" id="username" value={this.state.username} placeholder="Username" onChange={this.updateInputValue.bind(this)}/>
                  </Col>
              </FormGroup>
              <FormGroup row>
                <Label className="login-label" for="password" sm={2}>Password</Label>
                <Col sm={10}>
                    <Input type="password" name="password" id="password" value={this.state.password}  placeholder="Password" onChange={this.updateInputValue.bind(this)}/>
                </Col>
              </FormGroup>
            </Form>
            <Button color="dark" id="btn-login" onClick={this.login.bind(this)} className="btn-default btn btn-primary btn-large centerButton" type="submit">Log In</Button>{' '}
          </ModalBody>
          
        </Modal>
      </div>
    )
  }
}


export {LoginModal as Login}