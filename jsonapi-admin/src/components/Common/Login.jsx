import React from 'react';
import { Button, Modal, ModalHeader, ModalBody, ModalFooter } from 'reactstrap';
import { Form, FormGroup, Label, Input } from 'reactstrap';
import toastr from 'toastr'
import * as Param from '../../Config';
import Cookies from 'universal-cookie';

class LoginModal extends React.Component {
  constructor(props) {
    super(props)
    const cookies = new Cookies()
    var token = cookies.get('token')

    this.state = {
      modal: props.logged_in,
      username : 'user4',
      password : 'pass',
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
    });
  }

  login(){
    let URL = Param.default.URL
    let options = { headers: new Headers({ 'Authorization': `Basic ${btoa(this.state.username + ':' + this.state.password)}` })}
    fetch(`${URL}/Auth/token`, options)
      .then(function(response) {
        if(response.status !== 200){
          throw new Error('Authentication Failed')
        }
        return response.json();
      })
      .then((json) => {
          toastr.success('Authenticated')
          const cookies = new Cookies();
          cookies.set('token', json.token);
          this.toggle()
          window.location.reload()
      })
      .catch((error)=>{ toastr.error(error) } )
  }

  logout(){
      const cookies = new Cookies();
      cookies.remove('token');
      cookies.remove('session');
      document.location.href="/";
  }

  updateInputValue(evt) {
    let s = {}
    s[evt.target.name] = evt.target.value
    this.setState(s);
  }

  render() {

    var link
    var isOpen = false
    if(this.state.token && this.state.token !== 'false' ){
        link  = <span id="login" onClick={this.logout.bind(this)}>Logout</span>
    }
    else {
        link = <span id="login" onClick={this.toggle}>{this.props.logged_in ? 'Logout' : 'Login' }</span>
        isOpen = true
    }

    return (
      <div>
        {link}
        <Modal isOpen={isOpen} toggle={this.toggle} className={this.props.className}>
          <ModalHeader toggle={this.toggle}>{this.props.text}</ModalHeader>
          <ModalBody>
            <Form>
              <FormGroup>
                <Label for="username">Login</Label>
                <Input name="username" id="username" value={this.state.username} placeholder="Username" onChange={this.updateInputValue.bind(this)}/>
              </FormGroup>
              <FormGroup>
                <Label for="password">Password</Label>
                <Input type="password" name="password" id="password" value={this.state.password}  placeholder="Password" onChange={this.updateInputValue.bind(this)}/>
              </FormGroup>
            </Form>
          </ModalBody>
          <ModalFooter>
            <Button color="primary" onClick={this.login.bind(this)}>Log In</Button>{' '}
            <Button color="secondary" onClick={this.toggle}>Cancel</Button>
          </ModalFooter>
        </Modal>
      </div>
    );
  }
}

export default LoginModal;