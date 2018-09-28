import React from 'react';
import { connect } from 'react-redux'
import * as analyzejson from './analyzejson'
import { bindActionCreators } from 'redux'
import {
  Header,
  Grid,
  Form,
  Button,
  Input
} from 'semantic-ui-react'

var stylefloat = {
  // float: "left",
  marginTop: "10px",
  width: "55%"
}

var stylefloat1 = {
  float: "right",
  marginTop: "10px",
  width: "55%"
}


class Otheroption extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      collecitonkey: -1,
      otheroption: ['main_show', 'path', 'API', 'API_TYPE', 'menu', 'Title', 'request_args', 'disabled'],
      main_show: '',
      path: '',
      API: '',
      API_TYPE: '',
      menu: '',
      Title: '',
      request_args: ''
    }
    this.handleOnchange = this.handleOnchange.bind(this)
    this.handleformsubmit = this.handleformsubmit.bind(this)
  }

  getcollectionname(key_index) {
    let rlt = ''
    Object.keys(this.props.json).map(function(key, index) {
      if (index === key_index) {
        rlt = key
      }
      return true
    })
    return rlt
  }
  handleformsubmit(e) {
    e.preventDefault()
    let data = {
      collectionId: this.getcollectionname(this.props.index),
      main_show: this.state.main_show,
      path: this.state.path,
      API: this.state.API,
      API_TYPE: this.state.API_TYPE,
      menu: this.state.menu,
      Title: this.state.Title,
      disabled: this.state.disabled,
      request_args: this.state.request_args
    }
    this.props.analyze.change_other(data)
    
  }

  handleOnchange(e) {
    this.state[e.target.placeholder] = e.target.value
    let place = e.target.placeholder
    const value = e.target.value
    if (place === 'reference') place = 'main_show'
    this.setState({place: value})
  }

  render() {
    let KEY = ''
    if (this.state.collecitonkey !== this.props.index) {
      this.state.collecitonkey = this.props.index
      this.state.otheroption.map((key, index) => {
        this.state[key] = ''
        return true
      })
    }
    if (Object.keys(this.props.json).length !== 0) {
      Object.keys(this.props.json).map(function(okey, index) {
        if (index === this.props.index) {
          KEY = okey
        }
        return true
      },this)
      this.state.otheroption.map((key, index) => {
        if (this.state[key] === ''){
          this.state[key] = this.props.json[KEY][key]
          if (key === 'request_args') {
            this.state[key] = JSON.stringify(this.props.json[KEY][key])
          }
        }
        return true
      }, this)
    }
    return (
      <div>
        <Header as='h4'>Other Options</Header>
        <Grid.Column width={10}>
          <Form widths='equal' onSubmit={this.handleformsubmit}>
            {this.state.otheroption.map((item, index) => {
              let lb = item
              let type = 'text'
              if (item === 'main_show') lb = 'reference'
              if (item === 'disabled') type = 'checkbox'
              
              return(
                <div key={index}>
                  <Input 
                    type={type}
                    label={lb}
                    style={stylefloat}
                    placeholder={item}
                    value={this.state[item]}
                    onChange={this.handleOnchange}
                  />
                </div>
              )
            })}
            
            <Button disabled={Object.keys(this.props.json).length !== 0?false:true} type='submit' style={stylefloat1}>Change config</Button>
          </Form>
        </Grid.Column>
      </div>
    )
  }
}

const mapStateToProps = (state) => ({
  json: state.configReducer
})

const mapDispatchToProps = dispatch => ({
  analyze: bindActionCreators(analyzejson, dispatch)
})

export default connect(mapStateToProps, mapDispatchToProps)(Otheroption)
