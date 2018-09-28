import React from 'react';
import { connect } from 'react-redux';
import * as Param from '.././Config';
import { NavLink as RRNavLink } from 'react-router-dom';
import * as InputAction from '../action/InputAction'
import { bindActionCreators } from 'redux'
import {
  Collapse,
  Navbar,
  NavbarToggler,
  NavbarBrand,
  Nav,
  NavItem,
  NavLink,
  UncontrolledDropdown,
  DropdownToggle,
  DropdownMenu,
  InputGroup,
  InputGroupAddon,
  Input,
  DropdownItem } from 'reactstrap';

import Cookies from 'universal-cookie';

class HeaderNavContainer extends React.Component {
  constructor(props) {
    super(props)
    this.toggle = this.toggle.bind(this)
    this.state = {
      isOpen: false
    };
    this.change_url = this.change_url.bind(this)
  }
  toggle() {
    this.setState({
      isOpen: !this.state.isOpen
    })
  }

  change_url(e){
    let api_url = e.target.value
    this.props.inputaction.getUrlAction(e.target.value);
    localStorage.setItem('url',api_url);
    const cookies = new Cookies()
    cookies.set('api_url', api_url)
  }

  render() {
    //let classname =  this.props.currentPath == Param.APP[key].path ? "current" : ""
    var currentPath = this.props.currentPath
    var currentStyle = {color:'white'} // todo move to css
    // var navTitle = Param.NavTitle ? Param.NavTitle : 'J:A'
    var navTitle = 'J:A'
    var INPUT = (<InputGroup className="Left">
                  <InputGroupAddon addonType="prepend">{this.props.inputflag.url===''?Param.URL:this.props.inputflag.url}</InputGroupAddon>
                </InputGroup>)
    if(this.props.inputflag.flag){
      INPUT =     (<InputGroup className="Left">
                    <InputGroupAddon addonType="prepend">Json:API Backend URL</InputGroupAddon>
                    <Input placeholder={this.props.inputflag.url===''?Param.URL:this.props.inputflag.url} onChange={this.change_url.bind(this)}/>
                  </InputGroup>)
    }

    // if(Param.disable_api_url){
    //     INPUT = ''
    // }

    // const login = Param.enable_login ?  <Login logged_in={logged_in}/> : 'Login'
    const login = 'Admin'

    return (
     <div>
        <Navbar color="faded" light expand="md" className="navbar-dark navbar-inverse bg-dark">
        <NavbarBrand replace tag={RRNavLink} to="/" >{navTitle}</NavbarBrand>
          <NavbarToggler onClick={this.toggle} />
          <Collapse isOpen={this.state.isOpen} navbar>
            <Nav navbar>
              {

                Object.keys(Param.APP).map(function(key, index){
                    if(Param.APP[key].hidden) {
                        return <span/>
                    }
                    return (<NavItem key = {index}>
                              <NavLink replace tag={RRNavLink} to={Param.APP[key].path} style={ currentPath === Param.APP[key].path ? currentStyle : {} }>
                                  {Param.APP[key].menu}
                              </NavLink>
                            </NavItem>)
                })
              }
            </Nav>
            {INPUT}
            <Nav className="ml-auto" navbar>
               <NavItem>
                <NavLink replace tag={RRNavLink} to="/Admin">{login}</NavLink>
              </NavItem>
              <UncontrolledDropdown nav inNavbar>
                <DropdownToggle nav caret>
                  {/* <FontAwesomeIcon icon={faCog}></FontAwesomeIcon> */}
                </DropdownToggle>
                <DropdownMenu right>
                  <DropdownItem>
                    <NavItem>
                      <NavLink replace tag={RRNavLink} to="/Admin">Admin</NavLink>
                    </NavItem>
                  </DropdownItem>
                  <DropdownItem>
                    <NavItem>
                      <NavLink replace tag={RRNavLink} to="/api">Api</NavLink>
                    </NavItem>
                  </DropdownItem>
                  <DropdownItem divider />
                   
                </DropdownMenu>
              </UncontrolledDropdown>
            </Nav>
          </Collapse>

        </Navbar>
      </div>
    )
  }
}

const mapStateToProps = state => ({
  api_data: state.object,
  inputflag: state.inputReducer
})

const mapDispatchToProps = dispatch => ({
  inputaction: bindActionCreators(InputAction,dispatch),
})

export default connect(mapStateToProps,mapDispatchToProps)(HeaderNavContainer);
